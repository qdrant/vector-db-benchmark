"""
Pinned 4-replica concurrency sweep with correct warmup.

The previous pinned-4r result (18.5 RPS) was broken: traffic hit replicas
before NVMe warmed. This script fixes that by:
  1. Pinning to 4 replicas and polling until ready_replicas=4/4
  2. Running a sequential warmup pass per replica (via round-robin routing)
  3. Sweeping concurrency levels and recording RPS/latency

Compared to the broken run, we expect to see proper horizontal scaling up to
~4× the single-replica ceiling (~370 RPS × 4 = ~1200–1400 RPS theoretical).
Saturation reveals whether S3 bandwidth or something else is the real ceiling.

Usage:
    cd ~/vector-db-benchmark
    source .env
    python scripts/probe_pinned4r.py [--queries-per-level 300] [--ns NAME]
"""

import argparse
import asyncio
import json
import os
import time

import numpy as np
import turbopuffer as tpuf

DATASET_QUERIES = "datasets/dbpedia-openai-100K-1536-angular/dbpedia_openai_100K/tests.jsonl"
DEFAULT_NS = "dbpedia-openai-100K-1536-angular"
CONCURRENCY_LEVELS = [1, 4, 8, 16, 32, 64, 128]
DEFAULT_QPL = 300
WARM_THRESHOLD_MS = 25
REPLICAS = 4


def load_queries(path, n=2000):
    queries = []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            queries.append(d["query"])
            if len(queries) >= n:
                break
    return queries


async def run_at_concurrency(ns, queries, concurrency, n_queries):
    semaphore = asyncio.Semaphore(concurrency)
    latencies = []

    async def query_one(vec):
        async with semaphore:
            t0 = time.perf_counter()
            await ns.query(rank_by=("vector", "ANN", vec), top_k=10, include_attributes=False)
            latencies.append(time.perf_counter() - t0)

    t_start = time.perf_counter()
    await asyncio.gather(*[query_one(queries[i % len(queries)]) for i in range(n_queries)])
    total = time.perf_counter() - t_start

    lats = np.array(latencies) * 1000
    return {
        "concurrency": concurrency,
        "n_queries": n_queries,
        "total_time_s": round(total, 3),
        "rps": round(n_queries / total, 1),
        "mean_ms": round(float(lats.mean()), 1),
        "p50_ms": round(float(np.percentile(lats, 50)), 1),
        "p95_ms": round(float(np.percentile(lats, 95)), 1),
        "p99_ms": round(float(np.percentile(lats, 99)), 1),
    }


async def wait_for_replicas(ns, target, timeout_s=300):
    print(f"  Waiting for ready_replicas >= {target}...")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        meta = await ns.metadata()
        pinning = getattr(meta, "pinning", None)
        status = getattr(pinning, "status", None) if pinning else None
        ready = getattr(status, "ready_replicas", 0) if status else 0
        total = getattr(pinning, "replicas", target) if pinning else target
        print(f"    ready_replicas={ready}/{total}")
        if ready >= target:
            return True
        await asyncio.sleep(10)
    print("  Timed out waiting for replicas")
    return False


async def warmup(ns, queries, target_ms=WARM_THRESHOLD_MS, max_queries=200):
    """
    Sequential warmup until rolling mean < target_ms.
    With 4 replicas, turbopuffer round-robins requests, so we need
    enough queries to warm all 4 NVMe caches.
    """
    print(f"  Warming up (target rolling mean <{target_ms}ms, up to {max_queries} queries)...")
    window = []
    for i in range(max_queries):
        t0 = time.perf_counter()
        await ns.query(
            rank_by=("vector", "ANN", queries[i % len(queries)]),
            top_k=10, include_attributes=False,
        )
        lat_ms = (time.perf_counter() - t0) * 1000
        window.append(lat_ms)
        if len(window) > 20:
            window.pop(0)
        mean = np.mean(window)
        if i >= 19 and mean < target_ms:
            print(f"  Warm after {i+1} queries — rolling mean {mean:.1f}ms")
            return i + 1
        if i % 20 == 0:
            print(f"    q{i}: {lat_ms:.0f}ms (rolling mean {mean:.1f}ms)")
    print(f"  Not fully warm after {max_queries} queries (mean={np.mean(window):.1f}ms) — proceeding")
    return max_queries


async def main(ns_name, n_per_level):
    api_key = os.environ["TURBOPUFFER_API_KEY"]
    region = os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2")

    client = tpuf.AsyncTurbopuffer(api_key=api_key, region=region)
    ns = client.namespace(ns_name)

    queries = load_queries(DATASET_QUERIES)
    print(f"Loaded {len(queries)} queries")

    try:
        # 1. Pin to 4 replicas
        print(f"\nPhase 1: Pinning '{ns_name}' to {REPLICAS} replicas...")
        await ns.update_metadata(pinning={"replicas": REPLICAS})
        ready = await wait_for_replicas(ns, target=REPLICAS)
        if not ready:
            print("ERROR: replicas not ready in time, aborting")
            return

        print(f"  All {REPLICAS} replicas ready")

        # 2. Warmup — need enough queries to cover all 4 replicas' NVMe caches
        print(f"\nPhase 2: Warming up all {REPLICAS} replicas...")
        n_warmup = await warmup(ns, queries)

        # 3. Concurrency sweep
        print(f"\nPhase 3: Concurrency sweep (p=1→{CONCURRENCY_LEVELS[-1]}, {n_per_level} queries each)...")
        results = []
        for c in CONCURRENCY_LEVELS:
            r = await run_at_concurrency(ns, queries, c, n_per_level)
            results.append(r)
            print(f"  p={c:3d}  RPS={r['rps']:7.1f}  mean={r['mean_ms']:6.1f}ms  p99={r['p99_ms']:.1f}ms")
            await asyncio.sleep(1)

        # Summary table
        print(f"\n{'='*60}")
        print(f"Pinned {REPLICAS}-replica concurrency sweep")
        print(f"{'='*60}")
        rps_p1 = results[0]["rps"]
        print(f"{'p':>5} | {'RPS':>8} | {'RPS/p1':>7} | {'mean':>8} | {'p95':>8} | {'p99':>8}")
        print("-" * 60)
        for r in results:
            ratio = r["rps"] / rps_p1
            print(f"  {r['concurrency']:3d} | {r['rps']:8.1f} | {ratio:7.2f}x | {r['mean_ms']:7.1f}ms | {r['p95_ms']:7.1f}ms | {r['p99_ms']:7.1f}ms")

        # Compare to single-replica baseline
        print(f"\nSingle-replica pinned 1r p=8: 212 RPS (from prior benchmark)")
        peak = max(r["rps"] for r in results)
        print(f"Pinned 4r peak: {peak:.0f} RPS  ({peak/212:.2f}× vs 1r baseline)")

        # Save
        ts = int(time.time())
        fname = f"results/probe-pinned4r-{ts}.json"
        with open(fname, "w") as f:
            json.dump({
                "experiment": "pinned_4r_correct_warmup",
                "namespace": ns_name,
                "replicas": REPLICAS,
                "queries_per_level": n_per_level,
                "n_warmup_queries": n_warmup,
                "results": results,
            }, f, indent=2)
        print(f"\nSaved to {fname}")

    finally:
        # Always unpin
        print("\nUnpinning namespace...")
        try:
            await ns.update_metadata(pinning=None)
            print("Unpinned.")
        except Exception as e:
            print(f"Warning: unpin failed: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries-per-level", type=int, default=DEFAULT_QPL)
    parser.add_argument("--ns", default=DEFAULT_NS)
    args = parser.parse_args()
    asyncio.run(main(args.ns, args.queries_per_level))
