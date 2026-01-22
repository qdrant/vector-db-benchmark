import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

QDRANT_URIS = os.getenv("QDRANT_URIS", "http://localhost:6333").split(",")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
DATASET_NAME = os.getenv("DATASET_NAME", "dbpedia-openai-100K-1536-angular")
RUNS = int(os.getenv("RUNS", 3))
OUTPUT_FILENAME = os.getenv("OUTPUT_FILENAME", "output.json")
WORK_DIR = Path(os.getenv("WORK_DIR", Path(__file__).parent))

COLLECTION_NAME = "benchmark"
VECTORS_FILE = WORK_DIR / "data" / DATASET_NAME / "vectors.npy"


@dataclass
class TransferMetrics:
    num_points: int = 0
    vector_dims: int = 0
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def throughput(self) -> float:
        return self.num_points / self.duration if self.duration > 0 else 0

    @property
    def mbps(self) -> float:
        bytes_tx = self.num_points * self.vector_dims * 4
        return (bytes_tx / 1024 / 1024) / self.duration if self.duration > 0 else 0


@dataclass
class BenchmarkResult:
    params: dict = field(default_factory=dict)
    runs: list[TransferMetrics] = field(default_factory=list)

    def stats(self) -> dict:
        if not self.runs:
            return {}
        durations = [r.duration for r in self.runs]
        throughputs = [r.throughput for r in self.runs]
        mbps_list = [r.mbps for r in self.runs]
        return {
            "runs": len(self.runs),
            "duration_mean": round(statistics.mean(durations), 3),
            "duration_std": round(statistics.stdev(durations), 3) if len(durations) > 1 else 0,
            "throughput_mean": round(statistics.mean(throughputs), 1),
            "throughput_std": round(statistics.stdev(throughputs), 1) if len(throughputs) > 1 else 0,
            "mbps_mean": round(statistics.mean(mbps_list), 2),
            "mbps_std": round(statistics.stdev(mbps_list), 2) if len(mbps_list) > 1 else 0,
        }

    def to_dict(self) -> dict:
        return {
            "name": "transfer_speed",
            "params": self.params,
            "stats": self.stats(),
            "timestamp": datetime.now().isoformat(),
        }


class TransferBenchmark:
    def __init__(self, uris: list[str], api_key: str | None = None):
        self.uris = uris
        self.clients = {uri: QdrantClient(url=uri, api_key=api_key, prefer_grpc=True, grpc_port=6334) for uri in uris}
        self.primary = self.clients[uris[0]]

    def setup_collection(self, dims: int):
        try:
            self.primary.delete_collection(COLLECTION_NAME)
            time.sleep(1)
        except Exception:
            pass

        self.primary.create_collection(
            COLLECTION_NAME,
            vectors_config=models.VectorParams(size=dims, distance=models.Distance.COSINE, on_disk=True),
            # Set to 0 to disable automatic indexing during upload
            optimizers_config=models.OptimizersConfigDiff(indexing_threshold=0),
        )

    def upload_vectors(self, vectors: np.ndarray):
        print(f"Uploading {len(vectors):,} vectors...")
        self.primary.upload_collection(
            collection_name=COLLECTION_NAME,
            vectors=vectors,
            ids=range(len(vectors)),
        )
        self.primary.update_collection(
            collection_name=COLLECTION_NAME,
            optimizer_config=models.OptimizersConfigDiff(indexing_threshold=1),
        )

    def wait_for_green(self, timeout: int = 600):
        print("Waiting for green status...", end="", flush=True)
        start = time.time()
        while time.time() - start < timeout:
            info = self.primary.get_collection(COLLECTION_NAME)
            if info.status == models.CollectionStatus.GREEN:
                print(f" done ({time.time() - start:.1f}s)")
                return
            time.sleep(1)
            print(".", end="", flush=True)
        print(f" timeout after {timeout}s")

    def get_collection_cluster_info(self) -> dict:
        return self.primary.http.distributed_api.collection_cluster_info(COLLECTION_NAME).dict()["result"]

    def wait_for_transfer_complete(self, timeout: int = 600):
        start = time.time()
        while time.time() - start < timeout:
            info = self.get_collection_cluster_info()
            if not info.get("shard_transfers"):
                return
            time.sleep(0.5)

    def start_transfer(self, shard_id: int, from_peer: int, to_peer: int):
        self.primary.http.distributed_api.update_collection_cluster(
            collection_name=COLLECTION_NAME,
            cluster_operations=models.ReplicateShardOperation(
                replicate_shard=models.ReplicateShard(
                    shard_id=shard_id,
                    from_peer_id=from_peer,
                    to_peer_id=to_peer,
                    method=models.ShardTransferMethod("stream_records"),
                ),
            ),
        )

    def drop_replica(self, shard_id: int, peer_id: int):
        self.primary.http.distributed_api.update_collection_cluster(
            collection_name=COLLECTION_NAME,
            cluster_operations=models.DropReplicaOperation(
                drop_replica=models.Replica(shard_id=shard_id, peer_id=peer_id),
            ),
        )

    def run(self, vectors: np.ndarray, runs: int) -> BenchmarkResult:
        num_points = len(vectors)
        dims = vectors.shape[1]

        print(f"\nDataset: {DATASET_NAME}")
        print(f"Points: {num_points:,}, Dims: {dims}, Runs: {runs}")

        self.setup_collection(dims)
        self.upload_vectors(vectors)
        self.wait_for_green()

        info = self.get_collection_cluster_info()
        from_peer = info["peer_id"]
        local_shards = info.get("local_shards", [])

        if not local_shards:
            print("Error: No local shards found")
            sys.exit(1)

        shard_id = local_shards[0]["shard_id"]

        # Find destination peer
        to_peer = None
        for uri, client in self.clients.items():
            node_info = client.http.distributed_api.collection_cluster_info(COLLECTION_NAME).dict()["result"]
            if node_info["peer_id"] != from_peer:
                to_peer = node_info["peer_id"]
                node_shards = {s["shard_id"] for s in node_info.get("local_shards", [])}
                if shard_id in node_shards:
                    self.drop_replica(shard_id, to_peer)
                    time.sleep(2)
                break

        if to_peer is None:
            print("Error: No destination peer found")
            sys.exit(1)

        print(f"Transfer: peer {from_peer} -> peer {to_peer}, shard {shard_id}")

        result = BenchmarkResult(params={
            "dataset": DATASET_NAME,
            "points": num_points,
            "dims": dims,
        })

        for i in range(runs):
            print(f"\nRun {i + 1}/{runs}:")
            if i > 0:
                self.drop_replica(shard_id, to_peer)
                time.sleep(2)

            metrics = TransferMetrics(num_points=num_points, vector_dims=dims)
            metrics.start_time = time.time()
            self.start_transfer(shard_id, from_peer, to_peer)
            self.wait_for_transfer_complete()
            metrics.end_time = time.time()

            print(f"  {metrics.duration:.2f}s, {metrics.throughput:,.0f} pts/s, {metrics.mbps:.2f} MB/s")
            result.runs.append(metrics)

        s = result.stats()
        print(f"\nSUMMARY: {s['throughput_mean']:,.0f} pts/s, {s['mbps_mean']:.2f} MB/s")

        return result

    def close(self):
        for client in self.clients.values():
            client.close()


def main():
    if not VECTORS_FILE.exists():
        print(f"Error: {VECTORS_FILE} not found")
        sys.exit(1)

    vectors = np.load(VECTORS_FILE)
    print(f"Loaded {len(vectors):,} vectors ({vectors.shape[1]} dims)")

    benchmark = TransferBenchmark(QDRANT_URIS, QDRANT_API_KEY)
    try:
        result = benchmark.run(vectors, RUNS)
        with open(OUTPUT_FILENAME, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
        print(f"Results saved to: {OUTPUT_FILENAME}")
    finally:
        benchmark.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()