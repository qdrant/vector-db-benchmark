"""
Test whether pinned turbopuffer replicas share machines with each other.

Pins two namespaces to 1 replica each, waits for both to be NVMe-warm,
then runs the same cross-namespace contention test as probe_contention.py.

Interpretation:
  victim p50 degrades > 50%  → pinned replicas still share a machine
                                (per-user routing applies to pinned too)
  victim p50 unchanged (<20%) → pinned replicas land on separate machines
                                (pinning buys isolation, not just NVMe residency)

Both namespaces are unpinned in a finally block regardless of outcome.

Usage:
  python scripts/probe_pinned_contention.py
  python scripts/probe_pinned_contention.py --ns-a foo --ns-b bar
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import numpy as np
import turbopuffer as tpuf

# ── Config ────────────────────────────────────────────────────────────────────
DEFAULT_NS_A  = "dbpedia-openai-100K-1536-angular"
DEFAULT_NS_B  = "dbpedia-coldtest"
DATASET_PATH  = "datasets/dbpedia-openai-100K-1536-angular/dbpedia_openai_100K/tests.jsonl"
DIMS          = 1536
REPLICAS      = 1

N_WARM        = 40    # sequential warmup per namespace
N_BASELINE    = 120   # victim queries, no aggressor
N_CONTENTION  = 180   # victim queries, under aggressor load
AGG_CONC      = 32    # aggressor concurrency

READY_POLL_S  = 10    # seconds between ready_replicas checks
READY_TIMEOUT = 300   # max seconds to wait for pinning


# ── Query loading ─────────────────────────────────────────────────────────────
def load_queries(n=600):
    p = Path(DATASET_PATH)
    if p.exists():
        qs = []
        with open(p) as f:
            for line in f:
                qs.append(json.loads(line)["query"])
                if len(qs) >= n:
                    break
        print(f"  Loaded {len(qs)} queries from {p.name}")
        return qs
    print(f"  Dataset not found, generating {n} random {DIMS}-dim unit vectors")
    rng = np.random.default_rng(42)
    v = rng.standard_normal((n, DIMS)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    return v.tolist()


# ── Pinning helpers ───────────────────────────────────────────────────────────
async def pin_and_wait(ns, replicas=REPLICAS, timeout=READY_TIMEOUT):
    print(f"  [{ns.id}] pinning to {replicas} replica(s)...")
    await ns.update_metadata(pinning={"replicas": replicas})
    deadline = time.time() + timeout
    while time.time() < deadline:
        meta  = await ns.metadata()
        pin   = getattr(meta, "pinning", None)
        st    = getattr(pin, "status", None) if pin else None
        ready = getattr(st, "ready_replicas", 0) if st else 0
        total = getattr(pin, "replicas", replicas) if pin else replicas
        print(f"  [{ns.id}] ready_replicas={ready}/{total}")
        if ready >= replicas:
            print(f"  [{ns.id}] pinned ✓")
            return True
        await asyncio.sleep(READY_POLL_S)
    print(f"  [{ns.id}] timed out waiting for pinning")
    return False


async def unpin(ns):
    try:
        await ns.update_metadata(pinning=None)
        print(f"  [{ns.id}] unpinned")
    except Exception as e:
        print(f"  [{ns.id}] unpin failed: {e}")


# ── Core async primitives ─────────────────────────────────────────────────────
async def warm_namespace(ns, queries, n=N_WARM):
    print(f"  [{ns.id}] warming ({n} sequential queries)...")
    lats = []
    for i in range(n):
        t0 = time.perf_counter()
        await ns.query(
            rank_by=("vector", "ANN", queries[i % len(queries)]),
            top_k=10,
            include_attributes=False,
        )
        lats.append((time.perf_counter() - t0) * 1000)
    arr = np.array(lats)
    print(f"  [{ns.id}] warm: mean={arr.mean():.1f}ms  p99={np.percentile(arr,99):.1f}ms")


async def victim_sequential(ns, queries, n):
    lats = []
    for i in range(n):
        t0 = time.perf_counter()
        await ns.query(
            rank_by=("vector", "ANN", queries[i % len(queries)]),
            top_k=10,
            include_attributes=False,
        )
        lats.append((time.perf_counter() - t0) * 1000)
    return lats


async def aggressor_sustained(ns, queries, concurrency, stop_event):
    pending: set = set()
    n_done = 0

    async def do_one(vec):
        nonlocal n_done
        try:
            await ns.query(
                rank_by=("vector", "ANN", vec),
                top_k=10,
                include_attributes=False,
            )
            n_done += 1
        except Exception:
            pass

    i = 0
    while True:
        pending -= {t for t in pending if t.done()}
        if stop_event.is_set():
            if not pending:
                break
            await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=1.0)
            continue
        while len(pending) < concurrency:
            t = asyncio.create_task(do_one(queries[i % len(queries)]))
            pending.add(t)
            i += 1
        await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=0.5)
    return n_done


async def run_phase(label, ns_victim, queries, n_victim,
                    ns_aggressor=None, agg_concurrency=AGG_CONC):
    print(f"\n── {label}")
    if ns_aggressor is None:
        lats = await victim_sequential(ns_victim, queries, n_victim)
        agg_n = 0
    else:
        stop      = asyncio.Event()
        agg_ready = asyncio.Event()

        async def aggressor_task():
            ramp = [
                asyncio.create_task(
                    ns_aggressor.query(
                        rank_by=("vector", "ANN", queries[i % len(queries)]),
                        top_k=10,
                        include_attributes=False,
                    )
                )
                for i in range(agg_concurrency)
            ]
            await asyncio.gather(*ramp, return_exceptions=True)
            sustained = asyncio.create_task(
                aggressor_sustained(ns_aggressor, queries, agg_concurrency, stop)
            )
            agg_ready.set()
            return agg_concurrency + await sustained

        async def victim_task():
            await agg_ready.wait()
            lats = await victim_sequential(ns_victim, queries, n_victim)
            stop.set()
            return lats

        lats, agg_n = await asyncio.gather(victim_task(), aggressor_task())

    arr = np.array(lats)
    print(
        f"  victim  n={len(lats)}"
        f"  mean={arr.mean():.1f}ms"
        f"  p50={np.percentile(arr,50):.1f}ms"
        f"  p95={np.percentile(arr,95):.1f}ms"
        f"  p99={np.percentile(arr,99):.1f}ms"
        f"  max={arr.max():.1f}ms"
    )
    if agg_n:
        print(f"  aggressor fired {agg_n} queries at p={agg_concurrency}")
    return lats


def stats(lats):
    a = np.array(lats)
    return dict(
        n=len(lats),
        mean=round(float(a.mean()), 2),
        p50=round(float(np.percentile(a, 50)), 2),
        p95=round(float(np.percentile(a, 95)), 2),
        p99=round(float(np.percentile(a, 99)), 2),
        max=round(float(a.max()), 2),
    )


def delta(base, cont, key):
    return f"{(cont[key] - base[key]) / base[key] * 100:+.1f}%"


# ── Main ──────────────────────────────────────────────────────────────────────
async def main(args):
    api_key = os.environ["TURBOPUFFER_API_KEY"]
    region  = os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2")
    client  = tpuf.AsyncTurbopuffer(api_key=api_key, region=region)

    ns_a = client.namespace(args.ns_a)
    ns_b = client.namespace(args.ns_b)

    print(f"Namespace A : {args.ns_a}")
    print(f"Namespace B : {args.ns_b}")
    print(f"Pinning     : {REPLICAS} replica each")
    print(f"Aggressor   : p={AGG_CONC}")

    queries = load_queries()

    try:
        # ── Phase 1: Pin both simultaneously ──────────────────────────────
        print("\n═══ Phase 1: Pin both namespaces ═══")
        ok_a, ok_b = await asyncio.gather(
            pin_and_wait(ns_a),
            pin_and_wait(ns_b),
        )
        if not (ok_a and ok_b):
            print("ERROR: one or both namespaces failed to pin. Aborting.")
            return

        await asyncio.sleep(3)

        # ── Phase 2: Warm both ────────────────────────────────────────────
        print("\n═══ Phase 2: Warm both pinned namespaces ═══")
        await warm_namespace(ns_a, queries)
        await warm_namespace(ns_b, queries)
        await asyncio.sleep(3)

        # ── Phase 3: Baselines ────────────────────────────────────────────
        print("\n═══ Phase 3: Baselines (pinned, no cross-namespace load) ═══")
        base_a = await run_phase(
            f"Baseline — victim=A  aggressor=none  [pinned]",
            ns_a, queries, N_BASELINE,
        )
        await asyncio.sleep(2)

        base_b = await run_phase(
            f"Baseline — victim=B  aggressor=none  [pinned]",
            ns_b, queries, N_BASELINE,
        )
        await asyncio.sleep(3)

        # ── Phase 4: Contention ───────────────────────────────────────────
        print("\n═══ Phase 4: Contention (both pinned) ═══")
        cont_a = await run_phase(
            f"Contention — victim=A  aggressor=B at p={AGG_CONC}  [both pinned]",
            ns_a, queries, N_CONTENTION, ns_b,
        )
        await asyncio.sleep(3)

        cont_b = await run_phase(
            f"Contention — victim=B  aggressor=A at p={AGG_CONC}  [both pinned]",
            ns_b, queries, N_CONTENTION, ns_a,
        )

        # ── Summary ───────────────────────────────────────────────────────
        print("\n═══ Summary ════════════════════════════════════════════════")
        rows = [("A as victim", base_a, cont_a), ("B as victim", base_b, cont_b)]
        verdicts = []
        for label, base, cont in rows:
            bs, cs = stats(base), stats(cont)
            print(f"\n  {label}  (pinned {REPLICAS}r each)")
            print(f"  {'metric':>6}  {'baseline':>10}  {'contention':>10}  {'delta':>8}")
            for k in ("mean", "p50", "p95", "p99"):
                print(f"  {k:>6}  {bs[k]:>8.1f}ms  {cs[k]:>8.1f}ms  {delta(bs, cs, k):>8}")

            ratio = (cs["p50"] - bs["p50"]) / bs["p50"]
            if ratio > 0.5:
                v = f"STRONG contention (p50 {delta(bs, cs, 'p50')}) — pinned replicas share a machine"
            elif ratio > 0.2:
                v = f"WEAK contention (p50 {delta(bs, cs, 'p50')}) — ambiguous"
            else:
                v = f"NO contention (p50 {delta(bs, cs, 'p50')}) — pinned replicas on separate machines"
            verdicts.append(f"  {label}: {v}")

        print("\n  Verdict:")
        for v in verdicts:
            print(f"  → {v}")

        # ── Save ──────────────────────────────────────────────────────────
        ts = int(time.time())
        out = {
            "experiment": "pinned_contention",
            "ns_a": args.ns_a,
            "ns_b": args.ns_b,
            "replicas": REPLICAS,
            "aggressor_concurrency": AGG_CONC,
            "n_baseline": N_BASELINE,
            "n_contention": N_CONTENTION,
            "baseline_a": stats(base_a),
            "baseline_b": stats(base_b),
            "contention_a_victim": stats(cont_a),
            "contention_b_victim": stats(cont_b),
        }
        fname = f"results/probe-pinned-contention-{ts}.json"
        with open(fname, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nSaved → {fname}")

    finally:
        print("\n═══ Unpinning both namespaces ═══")
        await asyncio.gather(unpin(ns_a), unpin(ns_b))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ns-a", default=DEFAULT_NS_A)
    parser.add_argument("--ns-b", default=DEFAULT_NS_B)
    asyncio.run(main(parser.parse_args()))
