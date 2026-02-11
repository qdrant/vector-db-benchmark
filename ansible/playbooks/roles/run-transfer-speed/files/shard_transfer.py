"""Benchmark shard transfer speed between Qdrant cluster nodes.

Uploads a dataset to a Qdrant cluster, then repeatedly replicates a shard
between two peers to measure transfer throughput (points/s and MB/s).
"""

import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import requests
from qdrant_client import QdrantClient, models

QDRANT_URIS = os.getenv("QDRANT_URIS", "http://localhost:6333").split(",")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
DATASET_NAME = os.getenv("DATASET_NAME", "laion-small-clip")
RUNS = int(os.getenv("RUNS", "3"))
OUTPUT_FILE = os.getenv("OUTPUT_FILENAME", "output.json")
WORK_DIR = Path(os.getenv("WORK_DIR", Path(__file__).parent))
COLLECTION = "benchmark"


class TransferBenchmark:
    def __init__(self, uris: list[str]):
        self.clients = {
            u: QdrantClient(
                url=u, api_key=QDRANT_API_KEY, prefer_grpc=True, grpc_port=6334
            )
            for u in uris
        }
        self.primary = self.clients[uris[0]]

    def cluster_info(self, client=None) -> models.CollectionClusterInfo:
        result = (
            (client or self.primary)
            .http.distributed_api.collection_cluster_info(COLLECTION)
            .result
        )
        assert result
        return result

    def setup(self, dims: int):
        try:
            self.primary.delete_collection(COLLECTION)
            time.sleep(1)
        except Exception:
            pass
        self.primary.create_collection(
            COLLECTION,
            vectors_config=models.VectorParams(
                size=dims, distance=models.Distance.COSINE, on_disk=True
            ),
            optimizers_config=models.OptimizersConfigDiff(
                default_segment_number=3,
                max_segment_size=1_000_000,
                memmap_threshold=10_000_000,
            ),
        )

    def upload(self, vectors: np.ndarray):
        n, batch = len(vectors), 1024
        for i in range(0, n, batch):
            self.primary.upsert(
                COLLECTION,
                points=models.Batch(
                    ids=list(range(i, min(i + batch, n))),
                    vectors=vectors[i : i + batch].tolist(),
                ),
                wait=False,
            )
        print(f"Uploaded {n:,} vectors")

    def wait_green(self, timeout=1800):
        t = 0
        while t < timeout:
            time.sleep(5)
            t += 5
            info = self.primary.get_collection(COLLECTION)
            if info.status == models.CollectionStatus.GREEN:
                time.sleep(5)
                if (
                    self.primary.get_collection(COLLECTION).status
                    == models.CollectionStatus.GREEN
                ):
                    return
        raise TimeoutError(f"Collection not green after {timeout}s")

    def storage_types(self, uri: str) -> Counter:
        try:
            data = requests.get(f"{uri}/telemetry?details_level=6", timeout=10).json()
            return Counter(
                vec["storage_type"]
                for coll in data["result"]["collections"]["collections"]
                if coll.get("id") == COLLECTION
                for shard in coll["shards"]
                for seg in (shard["local"] or {}).get("segments", [])
                for vec in seg["config"]["vector_data"].values()
            )
        except Exception as e:
            print(f"    Telemetry error: {e}")
        return Counter()

    def wait_mmap(self, uri: str, timeout=180):
        print("Waiting for Mmap segments...")
        start = time.time()
        types = Counter()
        while time.time() - start < timeout:
            types = self.storage_types(uri)
            mmap = types.get("Mmap", 0)
            chunked = types.get("ChunkedMmap", 0) + types.get("InRamChunkedMmap", 0)
            print(f"  Storage types: {types}")
            if mmap > 0 and mmap >= chunked:
                return
            time.sleep(5)
        print(f"Warning: Mmap timeout, continuing anyway. Types: {types}")

    def wait_transfer(self, timeout=600):
        start = time.time()
        while time.time() - start < timeout:
            if not self.cluster_info().shard_transfers:
                return
            time.sleep(0.5)
        raise TimeoutError("Transfer timeout")

    def replicate(self, shard_id: int, from_peer: int, to_peer: int):
        self.primary.http.distributed_api.update_collection_cluster(
            COLLECTION,
            cluster_operations=models.ReplicateShardOperation(
                replicate_shard=models.ReplicateShard(
                    shard_id=shard_id, from_peer_id=from_peer, to_peer_id=to_peer
                ),
            ),
        )

    def drop_replica(self, shard_id: int, peer_id: int):
        self.primary.http.distributed_api.update_collection_cluster(
            COLLECTION,
            cluster_operations=models.DropReplicaOperation(
                drop_replica=models.Replica(shard_id=shard_id, peer_id=peer_id),
            ),
        )

    def run(self, vectors: np.ndarray, runs: int) -> dict:
        n, dims = vectors.shape
        self.setup(dims)
        self.upload(vectors)
        self.wait_green()
        self.wait_mmap(list(self.clients.keys())[0])

        info = self.cluster_info()
        from_peer = info.peer_id
        shard_id = info.local_shards[0].shard_id

        to_peer = None
        for client in self.clients.values():
            node = self.cluster_info(client)
            if node.peer_id != from_peer:
                to_peer = node.peer_id
                if shard_id in {s.shard_id for s in node.local_shards}:
                    self.drop_replica(shard_id, to_peer)
                    time.sleep(2)
                break

        if not to_peer:
            raise RuntimeError("No destination peer")

        print(f"Transfer: {from_peer} -> {to_peer}, shard {shard_id}")
        durations = []
        for i in range(runs):
            if i > 0:
                self.drop_replica(shard_id, to_peer)
                time.sleep(2)
            start = time.time()
            self.replicate(shard_id, from_peer, to_peer)
            self.wait_transfer()
            dur = time.time() - start
            durations.append(dur)
            print(f"  Run {i+1}: {dur:.2f}s, {n/dur:,.0f} pts/s")

        bytes_per_point = dims * 4
        throughputs = [n / d for d in durations]
        mbps = [(n * bytes_per_point / 1024 / 1024) / d for d in durations]

        return {
            "name": "transfer_speed",
            "params": {"dataset": DATASET_NAME, "points": n, "dims": dims},
            "stats": {
                "runs": runs,
                "duration_mean": round(statistics.mean(durations), 3),
                "duration_std": (
                    round(statistics.stdev(durations), 3) if runs > 1 else 0
                ),
                "throughput_mean": round(statistics.mean(throughputs), 1),
                "mbps_mean": round(statistics.mean(mbps), 2),
            },
        }

    def close(self):
        for c in self.clients.values():
            c.close()


def main():
    vectors_file = WORK_DIR / "data" / DATASET_NAME / "vectors.npy"
    if not vectors_file.exists():
        sys.exit(f"Error: {vectors_file} not found")

    vectors = np.load(vectors_file)
    print(f"Dataset: {DATASET_NAME}, {len(vectors):,} x {vectors.shape[1]}d")

    bench = TransferBenchmark(QDRANT_URIS)
    try:
        result = bench.run(vectors, RUNS)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(result, f, indent=2)
        print(
            f"Result: {result['stats']['throughput_mean']:,.0f} pts/s, {result['stats']['mbps_mean']:.2f} MB/s"
        )
    finally:
        bench.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
