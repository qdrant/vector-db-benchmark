"""
Test Qdrant's indexing time after delete+upload a specified % of points.


This script will:

- Create a Qdrant collection, and make initial upload of all vectors.
- Select and remove a specified % of points.
- Upload a specified % of points and measure the time it takes to re-index the collection.

"""

import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

QDRANT_COLLECTION_NAME = "benchmark"
DATASET_DIM = int(os.getenv("DATASET_DIM", 1536))
DATASET_NAME = os.getenv("DATASET_NAME", "random_float_200k_1536")
DATASET_NAME_2 = os.getenv("DATASET_NAME_2", "random_float_200k_1536_2")
DATA_DIR = Path(__file__).parent / "data" / DATASET_NAME
DATA_DIR_2 = Path(__file__).parent / "data" / DATASET_NAME_2
OUTPUT_FILENAME = os.getenv("OUTPUT_FILENAME", "output.json")
POINTS_PERCENTAGE = int(os.getenv("POINTS_PERCENTAGE", 1))

VECTORS_FILE_2 = DATA_DIR_2 / "vectors.npy"
VECTORS_FILE_1 = DATA_DIR / "vectors.npy"

TOTAL_VECTORS = 200_000


def read_test_data(file: Path, limit: int = 1000):
    """
    {
        "query": [
            0.022043373435735703,
            -0.022230295464396477,
            ....
        ],
        "closest_ids": [
            43749,
            43756,
            ....
        ]
    }
    """
    with open(file, "r") as f:
        for idx, line in enumerate(f):
            if idx >= limit:
                break

            yield json.loads(line)


class QdrantBenchmark:

    def __init__(self, url):

        client = QdrantClient(url=url, prefer_grpc=True)
        self.client = client

        self.client.delete_collection(QDRANT_COLLECTION_NAME)

        self.collection = self.client.create_collection(
            QDRANT_COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=DATASET_DIM,
                distance=models.Distance.COSINE,
            ),
            optimizers_config=models.OptimizersConfigDiff(
                indexing_threshold=0, vacuum_min_vector_number=100
            ),
        )

    def initial_upload(self, vectors: np.ndarray):
        self.client.upload_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors=vectors,
            ids=range(len(vectors)),
        )

    def delete_points(self, points_to_delete: set):
        self.client.delete(
            collection_name=QDRANT_COLLECTION_NAME,
            points_selector=models.PointIdsList(
                points=[idx for idx in points_to_delete]
            ),
        )

    def upload_points(self, vectors: np.ndarray, ids: list[int], batch_size: int = 500):
        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            points = [
                models.PointStruct(id=idx, vector=vectors[idx].tolist()) for idx in batch_ids
            ]
            
            self.client.upsert(
                collection_name=QDRANT_COLLECTION_NAME,
                points=points,
            )

    def update_indexing_threshold(self, indexing_threshold: int):
        self.client.update_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            optimizer_config=models.OptimizersConfigDiff(
                indexing_threshold=indexing_threshold
            )
        )

    def wait_ready(self) -> float:
        wait_interval = 0.2
        confirmations_required = 2

        start_time = time.time()
        confirmations = 0
        first_green_time: float | None = None

        while True:
            collection_info = self.client.get_collection(QDRANT_COLLECTION_NAME)
            if collection_info.status == models.CollectionStatus.GREEN:
                confirmations += 1
                first_green_time = first_green_time or time.time()
                if confirmations == confirmations_required:
                    return first_green_time - start_time
            else:
                confirmations = 0
                first_green_time = None
            time.sleep(wait_interval)

    def __del__(self):
        self.client.close()


def store_to_file(data_dict):
    timestamped_dict = data_dict.copy()
    timestamped_dict["timestamp"] = datetime.now().isoformat()

    with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
        json.dump(timestamped_dict, f, ensure_ascii=False)


def main():
    result = {}
    vectors_1 = np.load(VECTORS_FILE_1)
    vectors_2 = np.load(VECTORS_FILE_2)

    benchmark = QdrantBenchmark("http://localhost:6333")
    benchmark.initial_upload(vectors_1)
    benchmark.wait_ready()

    # Calculate number of points to update based on percentage
    num_points_to_update = int(TOTAL_VECTORS * POINTS_PERCENTAGE / 100)
    # Select points to update
    points_to_update = random.sample(range(TOTAL_VECTORS), num_points_to_update)
    # benchmark.delete_points(points_to_update)
    benchmark.upload_points(vectors_2, points_to_update)
    benchmark.update_indexing_threshold(indexing_threshold=1)

    total_indexing_time = benchmark.wait_ready()

    print(f"Indexing: {total_indexing_time}")
    result["indexing_total_time_s"] = total_indexing_time

    store_to_file(result)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    main()

    sys.stdout.flush()
    sys.stderr.flush()
