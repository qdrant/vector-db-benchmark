"""
Compute core count probing experiment for turbopuffer.

Pins a namespace with 1 replica, waits for warm state, then sweeps concurrency
from p=1 to p=64. RPS will scale linearly up to the node's core count, then
flatten — the saturation point reveals how many effective cores turbopuffer
allocates per pinned replica.

Also runs the same sweep on serverless (unpinned) to compare: does the shared
pool allocate differently than a dedicated pinned node?

Usage:
    cd ~/vector-db-benchmark
    source .env
    python scripts/probe_cores.py [--queries-per-level 300] [--ns NAME]
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
CONCURRENCY_LEVELS = [1, 2, 4, 8, 16, 32, 64]
DEFAULT_QPL = 300   # queries per concurrency level
WARM_THRESHOLD_MS = 30


def load_queries(path, n=1000):
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


async def warmup(ns, queries, target_ms=WARM_THRESHOLD_MS, max_queries=100):
    """Sequential warmup until rolling mean < target_ms."""
    print(f"  Warming up (target <{target_ms}ms rolling mean)...")
    window = []
    for i in range(max_queries):
        t0 = time.perf_counter()
        await ns.query(rank_by=("vector", "ANN", queries[i % len(queries)]), top_k=10, include_attributes=False)
        lat_ms = (time.perf_counter() - t0) * 1000
        window.append(lat_ms)
        if len(window) > 10:
            window.pop(0)
        if i >= 9 and np.mean(window) < target_ms:
            print(f"  Warm after {i+1} queries — rolling mean {np.mean(window):.1f}ms")
            return
        if i % 20 == 0:
            print(f"    q{i}: {lat_ms:.0f}ms")
    print(f"  Not fully warm after {max_queries} queries — proceeding anyway")


async def wait_for_replicas(ns, target=1, timeout_s=300):
    """Poll namespace metadata until ready_replicas >= target."""
    print(f"  Waiting for ready_replicas >= {target}...")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        meta = await ns.metadata()
        pinning = getattr(meta, "pinning", None)
        if pinning:
            status = getattr(pinning, "status", None)
            ready = getattr(status, "ready_replicas", 0) if status else 0
            total = getattr(pinning, "replicas", 1)
            print(f"    ready_replicas={ready}/{total}")
            if ready >= target:
                return True
        await asyncio.sleep(5)
    print("  Timed out waiting for replicas")
    return False


async def sweep(ns, queries, label, n_per_level):
    print(f"\n{'='*50}")
    print(f"Sweeping concurrency: {label}")
    print(f"{'='*50}")
    results = []
    for c in CONCURRENCY_LEVELS:
        r = await run_at_concurrency(ns, queries, c, n_per_level)
        results.append(r)
        print(f"  p={c:2d}  →  RPS={r['rps']:6.1f}  mean={r['mean_ms']:6.1f}ms  p99={r['p99_ms']:.1f}ms")
        await asyncio.sleep(1)
    return results


def print_table(results, label):
    print(f"\n{label}")
    print(f"{'p':>4} | {'RPS':>8} | {'RPS/p1':>7} | {'mean':>8} | {'p99':>8}")
    print("-" * 50)
    rps_p1 = results[0]["rps"]
    for r in results:
        ratio = r["rps"] / rps_p1
        print(f"  {r['concurrency']:2d} | {r['rps']:8.1f} | {ratio:7.2f}x | {r['mean_ms']:7.1f}ms | {r['p99_ms']:.1f}ms")


async def main(ns_name, n_per_level):
    api_key = os.environ["TURBOPUFFER_API_KEY"]
    region = os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2")

    client = tpuf.AsyncTurbopuffer(api_key=api_key, region=region)
    ns = client.namespace(ns_name)

    queries = load_queries(DATASET_QUERIES)
    print(f"Loaded {len(queries)} queries")

    all_results = {}

    # --- Phase 1: Pinned 1-replica ---
    print(f"\nPhase 1: Pinned 1-replica")
    print(f"  Pinning namespace '{ns_name}' with 1 replica...")
    await ns.update_metadata(pinning={"replicas": 1})
    await wait_for_replicas(ns, target=1)
    await warmup(ns, queries)

    pinned_results = await sweep(ns, queries, "Pinned 1-replica", n_per_level)
    all_results["pinned_1r"] = pinned_results

    # --- Phase 2: Serverless (unpin) ---
    print(f"\nPhase 2: Serverless (unpinned)")
    print(f"  Unpinning namespace...")
    await ns.update_metadata(pinning=None)
    # The namespace data stays warm in the shared pool for a bit after unpin
    # We run queries immediately to capture warm serverless numbers
    await warmup(ns, queries, target_ms=50)

    serverless_results = await sweep(ns, queries, "Serverless (unpinned, warm)", n_per_level)
    all_results["serverless_warm"] = serverless_results

    # Save
    ts = int(time.time())
    fname = f"results/probe-cores-{ts}.json"
    with open(fname, "w") as f:
        json.dump({
            "experiment": "core_count_probe",
            "namespace": ns_name,
            "queries_per_level": n_per_level,
            "results": all_results,
        }, f, indent=2)
    print(f"\nSaved to {fname}")

    # Summary tables
    print_table(pinned_results, "Pinned 1-replica — RPS scaling")
    print_table(serverless_results, "Serverless warm — RPS scaling")

    # Saturation estimate
    for label, results in [("Pinned", pinned_results), ("Serverless", serverless_results)]:
        for i in range(1, len(results)):
            ratio = results[i]["rps"] / results[i-1]["rps"]
            if ratio < 1.5:  # less than 50% gain from doubling concurrency = saturating
                sat_p = results[i-1]["concurrency"]
                print(f"\n{label} saturation around p={sat_p} "
                      f"(RPS gain from p={results[i-1]['concurrency']} → p={results[i]['concurrency']}: {ratio:.2f}x)")
                break


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries-per-level", type=int, default=DEFAULT_QPL)
    parser.add_argument("--ns", default=DEFAULT_NS)
    args = parser.parse_args()
    asyncio.run(main(args.ns, args.queries_per_level))
