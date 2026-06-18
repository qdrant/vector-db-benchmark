"""
Cold warmup curve experiment for turbopuffer.

Sends N_QUERIES sequential queries to a cold namespace, recording per-query
latency to observe the SPFresh cache warmup curve: how many queries does it
take to transition from cold (~1-12s) to warm (~17ms)?

Use --cold-copy to create a guaranteed-cold namespace via copy_from (copies S3
objects into a fresh namespace with no NVMe cache) rather than waiting for an
existing namespace to expire.

Usage:
    cd ~/vector-db-benchmark
    source .env
    python scripts/probe_coldwarm.py [--queries 500] [--ns NAME] [--cold-copy]
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
COLD_NS = "dbpedia-coldtest"
DEFAULT_N = 500


def load_queries(path, n):
    queries = []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            queries.append(d["query"])
            if len(queries) >= n:
                break
    return queries


async def main(ns_name, n_queries, cold_copy):
    api_key = os.environ["TURBOPUFFER_API_KEY"]
    region = os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2")

    client = tpuf.AsyncTurbopuffer(api_key=api_key, region=region)

    if cold_copy:
        print(f"Creating cold copy '{COLD_NS}' from '{ns_name}' via copy_from...")
        cold_ns = client.namespace(COLD_NS)
        t0 = time.perf_counter()
        await cold_ns.copy_from(source_namespace=ns_name)
        print(f"  copy_from completed in {(time.perf_counter()-t0)*1000:.0f}ms")
        ns = cold_ns
        ns_name = COLD_NS
    else:
        ns = client.namespace(ns_name)

    queries = load_queries(DATASET_QUERIES, n_queries)
    print(f"Loaded {len(queries)} queries")

    # Probe warmth
    print(f"\nProbing namespace '{ns_name}' with first query...")
    t0 = time.perf_counter()
    await ns.query(rank_by=("vector", "ANN", queries[0]), top_k=10, include_attributes=False)
    probe_lat = (time.perf_counter() - t0) * 1000
    if probe_lat < 100:
        print(f"  WARNING: appears warm ({probe_lat:.0f}ms) — cold curve may be missed")
    else:
        print(f"  Cold confirmed ({probe_lat:.0f}ms)")

    print(f"\nRunning {n_queries} sequential queries (p=1)...\n")

    results = [{"i": 0, "latency_ms": probe_lat, "elapsed_s": 0.0}]
    print(f"  q{0:4d}: {probe_lat:8.1f}ms")
    t_start = time.time()

    for i, query in enumerate(queries[1:], start=1):
        t0 = time.perf_counter()
        await ns.query(rank_by=("vector", "ANN", query), top_k=10, include_attributes=False)
        lat_ms = (time.perf_counter() - t0) * 1000
        elapsed = time.time() - t_start

        results.append({"i": i, "latency_ms": lat_ms, "elapsed_s": elapsed})

        # Print first 20, then every 25
        if i < 20 or i % 25 == 0:
            print(f"  q{i:4d}: {lat_ms:8.1f}ms  (elapsed {elapsed:.1f}s)")

    # Save
    ts = int(time.time())
    fname = f"results/probe-coldwarm-{ts}.json"
    with open(fname, "w") as f:
        json.dump({
            "experiment": "cold_warmup_curve",
            "namespace": ns_name,
            "n_queries": len(results),
            "results": results,
        }, f)
    print(f"\nSaved to {fname}")

    # Summary
    lats = np.array([r["latency_ms"] for r in results])
    first10 = lats[:10]
    last20 = lats[-20:]

    # Find the query where we first hit "warm" (< 50ms)
    warm_threshold = 50
    warm_at = next((r["i"] for r in results if r["latency_ms"] < warm_threshold), None)

    print(f"\n{'='*50}")
    print(f"First 5 queries:  {[f'{l:.0f}ms' for l in lats[:5]]}")
    print(f"Last  5 queries:  {[f'{l:.0f}ms' for l in lats[-5:]]}")
    print(f"p50 overall:      {np.percentile(lats, 50):.0f}ms")
    print(f"p95 overall:      {np.percentile(lats, 95):.0f}ms")
    print(f"First warm query (<{warm_threshold}ms): q{warm_at}" if warm_at else f"Never reached <{warm_threshold}ms")
    if warm_at:
        elapsed_to_warm = results[warm_at]["elapsed_s"]
        print(f"Time to warm:     {elapsed_to_warm:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=int, default=DEFAULT_N)
    parser.add_argument("--ns", default=DEFAULT_NS)
    parser.add_argument("--cold-copy", action="store_true",
                        help="Create guaranteed-cold namespace via copy_from before running")
    args = parser.parse_args()
    asyncio.run(main(args.ns, args.queries, args.cold_copy))
