"""
Async Qdrant benchmark — single client, shared connection pool.
Eliminates per-worker TCP/TLS handshake overhead of the multiprocessing harness.
Mirrors async_tpuf_bench.py methodology for apples-to-apples comparison.

Usage (search):
  PYTHONUNBUFFERED=1 python scripts/async_qdrant_bench.py

Upload is supported but skipped by default since data is already loaded.
Set UPLOAD=1 to run upload before search.
"""

import asyncio
import os
import time

import numpy as np
from qdrant_client import AsyncQdrantClient, models

CONCURRENCY = int(os.environ.get("CONCURRENCY", "32"))
N_QUERIES = int(os.environ.get("N_QUERIES", "5000"))
COLLECTION_NAME = os.environ.get("QDRANT_COLLECTION_NAME", "benchmark")
HNSW_EF = int(os.environ.get("HNSW_EF", "128"))
DATASET_PATH = "datasets/dbpedia-openai-100K-1536-angular/dbpedia_openai_100K"
UPLOAD = os.environ.get("UPLOAD", "0") == "1"
BATCH_SIZE = 256


async def upload(client: AsyncQdrantClient, vectors: np.ndarray):
    print(f"Creating collection '{COLLECTION_NAME}'...")
    await client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=vectors.shape[1], distance=models.Distance.COSINE),
        hnsw_config=models.HnswConfigDiff(m=16, ef_construct=128),
        optimizers_config=models.OptimizersConfigDiff(memmap_threshold=10_000_000),
    )

    total = len(vectors)
    print(f"Uploading {total} vectors in batches of {BATCH_SIZE}...")
    t0 = time.perf_counter()
    for start in range(0, total, BATCH_SIZE):
        batch = vectors[start:start + BATCH_SIZE]
        points = [
            models.PointStruct(id=start + i, vector=v.tolist())
            for i, v in enumerate(batch)
        ]
        await client.upsert(collection_name=COLLECTION_NAME, points=points)
        if start % 10000 == 0:
            print(f"  {start}/{total}", flush=True)

    elapsed = time.perf_counter() - t0
    print(f"Upload done in {elapsed:.1f}s ({elapsed/60:.1f} min)")

    print("Waiting for indexing to complete...")
    while True:
        info = await client.get_collection(COLLECTION_NAME)
        if info.status == models.CollectionStatus.GREEN:
            break
        print(f"  status={info.status}, indexed={info.indexed_vectors_count}/{info.vectors_count}", flush=True)
        await asyncio.sleep(5)
    print("Collection ready.")


async def search(client: AsyncQdrantClient, vectors: np.ndarray):
    queries = vectors[:N_QUERIES].tolist()
    print(f"Loaded {len(queries)} query vectors")

    semaphore = asyncio.Semaphore(CONCURRENCY)
    latencies = []
    server_latencies = []

    async def query_one(vec):
        async with semaphore:
            t0 = time.perf_counter()
            raw = await client.http.search_api.query_points(
                collection_name=COLLECTION_NAME,
                query_request=models.QueryRequest(
                    query=vec,
                    params=models.SearchParams(hnsw_ef=HNSW_EF),
                    limit=10,
                    with_vector=False,
                    with_payload=False,
                ),
            )
            latencies.append(time.perf_counter() - t0)
            if raw.time is not None:
                server_latencies.append(raw.time)

    print(f"Starting {N_QUERIES} queries with concurrency={CONCURRENCY}, hnsw_ef={HNSW_EF}...")
    t_start = time.perf_counter()
    await asyncio.gather(*[query_one(q) for q in queries])
    total = time.perf_counter() - t_start

    lats = np.array(latencies)
    print(f"\nResults (async, concurrency={CONCURRENCY}, n={N_QUERIES}, hnsw_ef={HNSW_EF}):")
    print(f"  total_time: {total:.2f}s")
    print(f"  RPS:        {N_QUERIES / total:.2f}")
    print(f"  mean:       {lats.mean()*1000:.0f}ms")
    print(f"  p50:        {np.percentile(lats, 50)*1000:.0f}ms")
    print(f"  p95:        {np.percentile(lats, 95)*1000:.0f}ms")
    print(f"  p99:        {np.percentile(lats, 99)*1000:.0f}ms")
    if server_latencies:
        slats = np.array(server_latencies)
        print(f"  server_mean: {slats.mean()*1000:.2f}ms")
        print(f"  server_p95:  {np.percentile(slats, 95)*1000:.2f}ms")
        print(f"  server_p99:  {np.percentile(slats, 99)*1000:.2f}ms")


async def main():
    url = os.environ["QDRANT_CLUSTER_URL"]
    api_key = os.environ.get("QDRANT_API_KEY")

    client = AsyncQdrantClient(url=url, api_key=api_key, check_compatibility=False, timeout=60)

    vectors = np.load(f"{DATASET_PATH}/vectors.npy")
    print(f"Dataset: {vectors.shape[0]} vectors × {vectors.shape[1]} dims")

    if UPLOAD:
        await upload(client, vectors)

    await search(client, vectors)
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
