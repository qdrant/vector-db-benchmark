"""
Probe cross-namespace resource contention on turbopuffer.

Tests whether turbopuffer co-locates multiple namespaces on the same physical
machine by measuring whether hammering namespace A degrades query latency on B.

If A and B share CPU cores or NVMe bandwidth, sustained load on A will show up
as increased p50/p95/p99 latency on B's sequential queries.

Phases:
  1. Warm both namespaces (NVMe residency)
  2. Baseline A — victim=A, aggressor=none
  3. Baseline B — victim=B, aggressor=none
  4. Contention  — victim=A at p=1, aggressor=B at p=32
  5. Contention  — victim=B at p=1, aggressor=A at p=32 (reversed)

Interpretation:
  victim p50 degrades > 50%  → strong co-location (shared CPU or NVMe)
  victim p99 degrades > 100% → NVMe I/O or CPU saturation visible
  no degradation              → isolated machines OR per-tenant throttling

Defaults to:
  ns-a = dbpedia-openai-100K-1536-angular
  ns-b = dbpedia-coldtest              (copy_from of same dataset)

Both namespaces are 1536-dim so the same query set is reused.

Usage:
  python scripts/probe_contention.py
  python scripts/probe_contention.py --ns-a foo --ns-b bar --dims-b 768
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import numpy as np
import turbopuffer as tpuf

# ── Defaults ────────────────────────────────────────────────────────────────
DEFAULT_NS_A   = "dbpedia-openai-100K-1536-angular"
DEFAULT_NS_B   = "dbpedia-coldtest"
DEFAULT_DIMS   = 1536
DATASET_PATH   = "datasets/dbpedia-openai-100K-1536-angular/dbpedia_openai_100K/tests.jsonl"

N_WARM         = 40    # sequential warmup queries per namespace
N_BASELINE     = 150   # victim queries (no aggressor)
N_CONTENTION   = 200   # victim queries (under aggressor load)
AGG_CONCURRENCY = 32   # aggressor in-flight requests


# ── Query loading ─────────────────────────────────────────────────────────────
def load_queries(path, dims, n=600):
    if path:
        p = Path(path)
        if p.exists():
            qs = []
            with open(p) as f:
                for line in f:
                    qs.append(json.loads(line)["query"])
                    if len(qs) >= n:
                        break
            print(f"  Loaded {len(qs)} queries from {p.name}")
            return qs

    print(f"  No dataset at '{path}', generating {n} random {dims}-dim unit vectors")
    rng = np.random.default_rng(42)
    vecs = rng.standard_normal((n, dims)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs.tolist()


# ── Core async primitives ────────────────────────────────────────────────────
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
    print(f"  [{ns.id}] warm: mean={arr.mean():.1f}ms  p99={np.percentile(arr, 99):.1f}ms")


async def victim_sequential(ns, queries, n):
    """Run n sequential queries; return per-query latencies in ms."""
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
    """Maintain ~concurrency in-flight requests until stop_event is set."""
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
        # Reap completed
        finished = {t for t in pending if t.done()}
        pending -= finished

        # Stop filling if event is set; drain remaining
        if stop_event.is_set():
            if not pending:
                break
            await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=1.0)
            continue

        # Fill to concurrency
        while len(pending) < concurrency:
            t = asyncio.create_task(do_one(queries[i % len(queries)]))
            pending.add(t)
            i += 1

        await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED, timeout=0.5)

    return n_done


# ── Phase runner ─────────────────────────────────────────────────────────────
async def run_phase(label, ns_victim, queries_v, n_victim,
                    ns_aggressor=None, queries_a=None, agg_concurrency=AGG_CONCURRENCY):
    """
    Run one measurement phase.
    If ns_aggressor is None → baseline (no load).
    Returns (victim_latencies_ms, aggressor_query_count).
    """
    print(f"\n── {label}")

    if ns_aggressor is None:
        lats = await victim_sequential(ns_victim, queries_v, n_victim)
        agg_total = 0
    else:
        stop     = asyncio.Event()
        agg_ready = asyncio.Event()

        async def aggressor_task():
            # Ramp: fire one full batch so we're at speed before victim starts
            ramp = [
                asyncio.create_task(
                    ns_aggressor.query(
                        rank_by=("vector", "ANN", queries_a[i % len(queries_a)]),
                        top_k=10,
                        include_attributes=False,
                    )
                )
                for i in range(agg_concurrency)
            ]
            await asyncio.gather(*ramp, return_exceptions=True)

            # Start sustained loop before signalling ready
            sustained = asyncio.create_task(
                aggressor_sustained(ns_aggressor, queries_a, agg_concurrency, stop)
            )
            agg_ready.set()
            n_sustained = await sustained
            return agg_concurrency + n_sustained

        async def victim_task():
            await agg_ready.wait()  # wait until aggressor is at full speed
            lats = await victim_sequential(ns_victim, queries_v, n_victim)
            stop.set()
            return lats

        lats, agg_total = await asyncio.gather(victim_task(), aggressor_task())

    arr = np.array(lats)
    print(
        f"  victim  n={len(lats)}"
        f"  mean={arr.mean():.1f}ms"
        f"  p50={np.percentile(arr, 50):.1f}ms"
        f"  p95={np.percentile(arr, 95):.1f}ms"
        f"  p99={np.percentile(arr, 99):.1f}ms"
        f"  max={arr.max():.1f}ms"
    )
    if agg_total:
        print(f"  aggressor fired {agg_total} queries at p={agg_concurrency}")

    return lats, agg_total


# ── Stats helper ─────────────────────────────────────────────────────────────
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


def delta_str(base, cont):
    d = (cont - base) / base * 100
    return f"{d:+.1f}%"


# ── Main ──────────────────────────────────────────────────────────────────────
async def main(args):
    api_key = os.environ["TURBOPUFFER_API_KEY"]
    region  = os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2")
    client  = tpuf.AsyncTurbopuffer(api_key=api_key, region=region)

    ns_a = client.namespace(args.ns_a)
    ns_b = client.namespace(args.ns_b)

    print(f"Namespace A : {args.ns_a}  ({args.dims_a}-dim)")
    print(f"Namespace B : {args.ns_b}  ({args.dims_b}-dim)")
    print(f"Aggressor   : p={AGG_CONCURRENCY} concurrent queries")

    queries_a = load_queries(DATASET_PATH, args.dims_a)
    if args.queries_b:
        queries_b = load_queries(args.queries_b, args.dims_b)
    elif args.dims_b == args.dims_a:
        queries_b = queries_a  # same dims → reuse
    else:
        queries_b = load_queries("", args.dims_b)

    # ── Phase 1: Warm ──────────────────────────────────────────────────────
    print("\n═══ Phase 1: Warm both namespaces ═══")
    await warm_namespace(ns_a, queries_a)
    await warm_namespace(ns_b, queries_b)
    await asyncio.sleep(3)

    # ── Phase 2: Baselines ─────────────────────────────────────────────────
    print("\n═══ Phase 2: Baselines (no cross-namespace load) ═══")
    base_a, _ = await run_phase(
        f"Baseline — victim=A  aggressor=none",
        ns_a, queries_a, N_BASELINE,
    )
    await asyncio.sleep(2)

    base_b, _ = await run_phase(
        f"Baseline — victim=B  aggressor=none",
        ns_b, queries_b, N_BASELINE,
    )
    await asyncio.sleep(3)

    # ── Phase 3: Contention A-victim, B-aggressor ──────────────────────────
    print("\n═══ Phase 3: Contention ═══")
    cont_a, agg_n_a = await run_phase(
        f"Contention — victim=A  aggressor=B at p={AGG_CONCURRENCY}",
        ns_a, queries_a, N_CONTENTION,
        ns_b, queries_b, AGG_CONCURRENCY,
    )
    await asyncio.sleep(3)

    # ── Phase 4: Contention B-victim, A-aggressor ──────────────────────────
    cont_b, agg_n_b = await run_phase(
        f"Contention — victim=B  aggressor=A at p={AGG_CONCURRENCY}",
        ns_b, queries_b, N_CONTENTION,
        ns_a, queries_a, AGG_CONCURRENCY,
    )

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n═══ Summary ═══════════════════════════════════════════════════")
    rows = [
        ("A as victim  (aggressor=B)", base_a, cont_a),
        ("B as victim  (aggressor=A)", base_b, cont_b),
    ]
    conclusions = []
    for label, base, cont in rows:
        bs, cs = stats(base), stats(cont)
        print(f"\n  {label}")
        print(f"  {'metric':>6}  {'baseline':>10}  {'contention':>10}  {'delta':>8}")
        for k in ("mean", "p50", "p95", "p99"):
            print(f"  {k:>6}  {bs[k]:>8.1f}ms  {cs[k]:>8.1f}ms  {delta_str(bs[k], cs[k]):>8}")

        p50_ratio = (cs["p50"] - bs["p50"]) / bs["p50"]
        if p50_ratio > 0.50:
            verdict = f"STRONG co-location signal — p50 {delta_str(bs['p50'], cs['p50'])}"
        elif p50_ratio > 0.15:
            verdict = f"WEAK co-location signal — p50 {delta_str(bs['p50'], cs['p50'])}"
        else:
            verdict = f"no degradation — p50 {delta_str(bs['p50'], cs['p50'])}  (possibly isolated or rate-limited)"
        conclusions.append(f"  {label}: {verdict}")

    print("\n  Verdict:")
    for c in conclusions:
        print(f"  → {c}")

    # ── Save ───────────────────────────────────────────────────────────────
    ts  = int(time.time())
    out = {
        "experiment": "cross_namespace_contention",
        "ns_a": args.ns_a,
        "ns_b": args.ns_b,
        "dims_a": args.dims_a,
        "dims_b": args.dims_b,
        "aggressor_concurrency": AGG_CONCURRENCY,
        "n_baseline": N_BASELINE,
        "n_contention": N_CONTENTION,
        "baseline_a": stats(base_a),
        "baseline_b": stats(base_b),
        "contention_a_victim_b_aggressor": stats(cont_a),
        "contention_b_victim_a_aggressor": stats(cont_b),
    }
    fname = f"results/probe-contention-{ts}.json"
    with open(fname, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved → {fname}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ns-a",      default=DEFAULT_NS_A,  help="First namespace name")
    parser.add_argument("--ns-b",      default=DEFAULT_NS_B,  help="Second namespace name")
    parser.add_argument("--dims-a",    default=DEFAULT_DIMS, type=int, help="Dims for namespace A queries")
    parser.add_argument("--dims-b",    default=DEFAULT_DIMS, type=int, help="Dims for namespace B queries")
    parser.add_argument("--queries-b", default=None, help="Path to B's query JSONL (optional)")
    asyncio.run(main(parser.parse_args()))
