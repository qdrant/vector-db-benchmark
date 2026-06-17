import asyncio
import os
import time

import numpy as np
import turbopuffer as tpuf

N_QUERIES = 500
NS_NAME = "dbpedia-openai-100K-1536-angular"
CONCURRENCIES = [32, 64, 128]
REPLICA_COUNTS = [1, 2]


async def run_bench(ns, concurrency, label):
    vectors = np.load("datasets/dbpedia-openai-100K-1536-angular/dbpedia_openai_100K/vectors.npy")
    queries = vectors[:N_QUERIES].tolist()

    semaphore = asyncio.Semaphore(concurrency)
    latencies = []

    async def query_one(vec):
        async with semaphore:
            t0 = time.perf_counter()
            await ns.query(rank_by=("vector", "ANN", vec), top_k=10, include_attributes=False)
            latencies.append(time.perf_counter() - t0)

    t_start = time.perf_counter()
    await asyncio.gather(*[query_one(q) for q in queries])
    total = time.perf_counter() - t_start

    lats = np.array(latencies)
    print(f"{label:<30} rps={N_QUERIES/total:>6.1f}  mean={lats.mean()*1000:>5.0f}ms  "
          f"p50={np.percentile(lats,50)*1000:>5.0f}ms  p95={np.percentile(lats,95)*1000:>5.0f}ms  "
          f"p99={np.percentile(lats,99)*1000:>5.0f}ms", flush=True)


async def main():
    api_key = os.environ["TURBOPUFFER_API_KEY"]
    region = os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2")

    sync_client = tpuf.Turbopuffer(api_key=api_key, region=region)
    sync_ns = sync_client.namespace(NS_NAME)

    async_client = tpuf.AsyncTurbopuffer(api_key=api_key, region=region)
    async_ns = async_client.namespace(NS_NAME)

    print(f"{'Config':<30} {'RPS':>7}  {'mean':>7}  {'p50':>7}  {'p95':>7}  {'p99':>7}")
    print("-" * 75)

    for replicas in REPLICA_COUNTS:
        print(f"\nPinning with {replicas} replica(s)...", flush=True)
        t_pin_start = time.perf_counter()
        sync_ns.update_metadata(pinning={"replicas": replicas})
        while True:
            meta = sync_ns.metadata()
            ready = meta.pinning.status.ready_replicas if (meta.pinning and meta.pinning.status) else 0
            print(f"  ready_replicas={ready}/{replicas}", flush=True)
            if ready >= replicas:
                break
            await asyncio.sleep(10)
        pin_time = time.perf_counter() - t_pin_start
        print(f"  Ready in {pin_time:.1f}s!", flush=True)

        for c in CONCURRENCIES:
            label = f"pinned-{replicas}r  c={c}"
            await run_bench(async_ns, c, label)

    print("\nUnpinning...", flush=True)
    sync_ns.update_metadata(pinning=None)
    print("Done.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
