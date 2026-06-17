import asyncio
import json
import os
import time

import numpy as np
import turbopuffer as tpuf

CONCURRENCY = 128
N_QUERIES = 2000
NS_NAME = "dbpedia-openai-100K-1536-angular"

async def main():
    api_key = os.environ["TURBOPUFFER_API_KEY"]
    region = os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2")

    client = tpuf.AsyncTurbopuffer(api_key=api_key, region=region)
    ns = client.namespace(NS_NAME)

    vectors = np.load("datasets/dbpedia-openai-100K-1536-angular/dbpedia_openai_100K/vectors.npy")
    queries = vectors[:N_QUERIES].tolist()
    print(f"Loaded {len(queries)} query vectors")

    semaphore = asyncio.Semaphore(CONCURRENCY)
    latencies = []

    server_ids = set()

    async def query_one(vec):
        async with semaphore:
            t0 = time.perf_counter()
            result = await ns.query(rank_by=("vector", "ANN", vec), top_k=10, include_attributes=False)
            latencies.append(time.perf_counter() - t0)
            # capture any server/replica identity headers
            headers = getattr(result, '_response', None)
            if headers is None:
                headers = getattr(result, 'response', None)
            if headers is not None:
                for k, v in headers.headers.items():
                    if any(x in k.lower() for x in ['replica', 'server', 'node', 'host', 'via', 'x-']):
                        server_ids.add(f"{k}: {v}")

    print(f"Starting {N_QUERIES} queries with concurrency={CONCURRENCY}...")
    t_start = time.perf_counter()
    await asyncio.gather(*[query_one(q) for q in queries])
    total = time.perf_counter() - t_start

    lats = np.array(latencies)
    print(f"\nServer/replica headers seen: {server_ids if server_ids else '(none)'}")
    print(f"\nResults (async, concurrency={CONCURRENCY}, n={N_QUERIES}):")
    print(f"  total_time: {total:.2f}s")
    print(f"  RPS:        {N_QUERIES / total:.2f}")
    print(f"  mean:       {lats.mean()*1000:.0f}ms")
    print(f"  p50:        {np.percentile(lats, 50)*1000:.0f}ms")
    print(f"  p95:        {np.percentile(lats, 95)*1000:.0f}ms")
    print(f"  p99:        {np.percentile(lats, 99)*1000:.0f}ms")

if __name__ == "__main__":
    asyncio.run(main())
