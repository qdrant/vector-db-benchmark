"""
Probe per-user vs random/hash namespace routing on turbopuffer.

Creates one or more fresh UUID-named namespaces, uploads N random vectors,
then runs the cross-namespace contention test against dbpedia.

Interpretation:
  UUID namespace shows STRONG contention with dbpedia (~3-4× p50 increase)
    → all namespaces under one API key land on the same machine
    → per-user (or per-API-key) routing

  UUID namespace shows NO contention with dbpedia (<20% p50 change)
    → different machines → hash/random routing across a fleet
    → run multiple trials to estimate fleet size (--trials N)

The UUID names eliminate any hash-collision with existing namespaces, so
name-based routing cannot explain co-location.

Note: probe namespaces are NOT deleted automatically.
      To delete: tpuf namespace delete probe-routing-<uuid>

Usage:
  python scripts/probe_routing.py
  python scripts/probe_routing.py --trials 3   # test 3 fresh namespaces
  python scripts/probe_routing.py --n-vectors 5000
"""

import argparse
import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import numpy as np
import turbopuffer as tpuf

# ── Config ────────────────────────────────────────────────────────────────────
EXISTING_NS  = "dbpedia-openai-100K-1536-angular"
DIMS         = 1536
DATASET_PATH = "datasets/dbpedia-openai-100K-1536-angular/dbpedia_openai_100K/tests.jsonl"

N_VECTORS    = 10_000   # vectors to upload into each probe namespace
BATCH_SIZE   = 1_000    # upload batch size
N_WARM       = 30       # warmup queries before measuring
N_BASELINE   = 100      # victim queries with no aggressor
N_CONTENTION = 150      # victim queries under aggressor load
AGG_CONC     = 32       # aggressor concurrency


# ── Query loading ─────────────────────────────────────────────────────────────
def load_queries(n=500):
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
    vecs = rng.standard_normal((n, DIMS)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs.tolist()


# ── Upload probe namespace ────────────────────────────────────────────────────
async def create_probe_namespace(client, ns_name, n_vectors):
    """Upload n_vectors random unit vectors into a fresh namespace."""
    ns = client.namespace(ns_name)
    rng = np.random.default_rng(int(time.time()) % (2**31))

    print(f"  Uploading {n_vectors} random {DIMS}-dim vectors in batches of {BATCH_SIZE}...")
    t0 = time.perf_counter()
    for batch_start in range(0, n_vectors, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, n_vectors)
        ids = list(range(batch_start, batch_end))
        vecs = rng.standard_normal((batch_end - batch_start, DIMS)).astype(np.float32)
        vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
        await ns.write(
            upsert_columns={"id": ids, "vector": vecs.tolist()},
            distance_metric="cosine_distance",
        )
        print(f"    batch {batch_start}–{batch_end} done")

    elapsed = time.perf_counter() - t0
    print(f"  Upload done in {elapsed:.1f}s")
    return ns


# ── Async primitives (same as probe_contention.py) ────────────────────────────
async def warm_namespace(ns, queries, n=N_WARM):
    print(f"  [{ns.id}] warming ({n} queries)...")
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
        finished = {t for t in pending if t.done()}
        pending -= finished
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


async def run_phase(label, ns_victim, queries_v, n_victim,
                    ns_aggressor=None, queries_a=None):
    print(f"\n── {label}")
    if ns_aggressor is None:
        lats = await victim_sequential(ns_victim, queries_v, n_victim)
        agg_total = 0
    else:
        stop      = asyncio.Event()
        agg_ready = asyncio.Event()

        async def aggressor_task():
            ramp = [
                asyncio.create_task(
                    ns_aggressor.query(
                        rank_by=("vector", "ANN", queries_a[i % len(queries_a)]),
                        top_k=10,
                        include_attributes=False,
                    )
                )
                for i in range(AGG_CONC)
            ]
            await asyncio.gather(*ramp, return_exceptions=True)
            sustained = asyncio.create_task(
                aggressor_sustained(ns_aggressor, queries_a, AGG_CONC, stop)
            )
            agg_ready.set()
            return AGG_CONC + await sustained

        async def victim_task():
            await agg_ready.wait()
            lats = await victim_sequential(ns_victim, queries_v, n_victim)
            stop.set()
            return lats

        lats, agg_total = await asyncio.gather(victim_task(), aggressor_task())

    arr = np.array(lats)
    print(
        f"  victim  n={len(lats)}"
        f"  mean={arr.mean():.1f}ms"
        f"  p50={np.percentile(arr,50):.1f}ms"
        f"  p95={np.percentile(arr,95):.1f}ms"
        f"  p99={np.percentile(arr,99):.1f}ms"
    )
    if agg_total:
        print(f"  aggressor fired {agg_total} queries at p={AGG_CONC}")
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


def verdict(base_lats, cont_lats, probe_ns_name):
    bs = stats(base_lats)
    cs = stats(cont_lats)
    ratio = (cs["p50"] - bs["p50"]) / bs["p50"]
    if ratio > 0.5:
        v = f"STRONG contention (+{ratio*100:.0f}% p50) — likely SAME machine → per-user routing"
    elif ratio > 0.15:
        v = f"WEAK contention (+{ratio*100:.0f}% p50) — ambiguous; possibly same machine or interference"
    else:
        v = f"NO contention ({ratio*100:+.0f}% p50) — likely DIFFERENT machine → fleet/hash routing"
    return v, bs, cs


# ── Main ──────────────────────────────────────────────────────────────────────
async def main(args):
    api_key = os.environ["TURBOPUFFER_API_KEY"]
    region  = os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2")
    client  = tpuf.AsyncTurbopuffer(api_key=api_key, region=region)

    queries = load_queries()
    ns_existing = client.namespace(EXISTING_NS)

    print(f"\nFixed namespace : {EXISTING_NS}")
    print(f"Probe vectors   : {args.n_vectors} random {DIMS}-dim unit vectors per trial")
    print(f"Trials          : {args.trials}")
    print(f"Aggressor       : p={AGG_CONC}")

    # Warm the fixed namespace once
    print(f"\n═══ Warm fixed namespace ═══")
    await warm_namespace(ns_existing, queries)
    await asyncio.sleep(2)

    # Baseline: fixed namespace alone
    print(f"\n═══ Baseline (fixed namespace, no aggressor) ═══")
    base_fixed = await run_phase(
        f"Baseline — victim={EXISTING_NS}  aggressor=none",
        ns_existing, queries, N_BASELINE,
    )
    await asyncio.sleep(2)

    all_results = []

    for trial in range(args.trials):
        probe_name = f"probe-routing-{uuid.uuid4().hex[:12]}"
        print(f"\n{'═'*60}")
        print(f"Trial {trial+1}/{args.trials}: probe namespace = {probe_name}")
        print(f"{'═'*60}")

        # Upload
        print(f"\n── Upload ──")
        ns_probe = await create_probe_namespace(client, probe_name, args.n_vectors)
        await asyncio.sleep(2)

        # Warm probe
        print(f"\n── Warm probe namespace ──")
        await warm_namespace(ns_probe, queries)
        await asyncio.sleep(2)

        # Contention: fixed=victim, probe=aggressor
        cont_fixed = await run_phase(
            f"Contention — victim=dbpedia  aggressor={probe_name}  p={AGG_CONC}",
            ns_existing, queries, N_CONTENTION,
            ns_probe,    queries,
        )
        await asyncio.sleep(2)

        # Contention: probe=victim, fixed=aggressor
        cont_probe = await run_phase(
            f"Contention — victim={probe_name}  aggressor=dbpedia  p={AGG_CONC}",
            ns_probe,    queries, N_CONTENTION,
            ns_existing, queries,
        )
        await asyncio.sleep(2)

        v_fixed, bs_f, cs_f = verdict(base_fixed, cont_fixed, probe_name)
        base_probe = await run_phase(
            f"Baseline — victim={probe_name}  aggressor=none",
            ns_probe, queries, N_BASELINE,
        )
        v_probe, bs_p, cs_p = verdict(base_probe, cont_probe, probe_name)

        print(f"\n  Trial {trial+1} verdict:")
        print(f"    dbpedia as victim  → {v_fixed}")
        print(f"    probe   as victim  → {v_probe}")
        print(f"    probe namespace    : {probe_name} (not deleted — delete manually if desired)")

        all_results.append({
            "trial": trial + 1,
            "probe_namespace": probe_name,
            "n_vectors": args.n_vectors,
            "baseline_dbpedia": bs_f,
            "contention_dbpedia_victim": cs_f,
            "baseline_probe": bs_p,
            "contention_probe_victim": cs_p,
            "verdict_dbpedia_victim": v_fixed,
            "verdict_probe_victim": v_probe,
        })

    # ── Final summary ──────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"Final summary ({args.trials} trial(s))")
    print(f"{'═'*60}")
    co_located = sum(
        1 for r in all_results
        if (r["contention_dbpedia_victim"]["p50"] - r["baseline_dbpedia"]["p50"])
           / r["baseline_dbpedia"]["p50"] > 0.5
    )
    print(f"  Co-located trials : {co_located}/{args.trials}")
    if co_located == args.trials:
        print("  → All trials co-located. Strong evidence of PER-USER routing.")
        print("    Every namespace under this API key lands on the same machine.")
    elif co_located == 0:
        print("  → No trials co-located. Evidence of FLEET/HASH routing.")
        est_fleet = max(2, round(1 / (1 - (co_located / args.trials + 0.001))))
        print(f"    Rough fleet size estimate: ≥ {args.trials + 1} machines.")
    else:
        p_coloc = co_located / args.trials
        est_fleet = round(1 / p_coloc) if p_coloc > 0 else "∞"
        print(f"  → Mixed ({co_located}/{args.trials} co-located).")
        print(f"    Estimated fleet size: ~{est_fleet} machines (if random assignment).")

    ts = int(time.time())
    fname = f"results/probe-routing-{ts}.json"
    with open(fname, "w") as f:
        json.dump({
            "experiment": "routing_probe",
            "existing_ns": EXISTING_NS,
            "dims": DIMS,
            "aggressor_concurrency": AGG_CONC,
            "n_baseline": N_BASELINE,
            "n_contention": N_CONTENTION,
            "trials": all_results,
        }, f, indent=2)
    print(f"\nSaved → {fname}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--trials",    type=int, default=1,        help="Number of fresh UUID namespaces to test (default: 1)")
    parser.add_argument("--n-vectors", type=int, default=N_VECTORS, help="Vectors to upload per probe namespace (default: 10000)")
    asyncio.run(main(parser.parse_args()))
