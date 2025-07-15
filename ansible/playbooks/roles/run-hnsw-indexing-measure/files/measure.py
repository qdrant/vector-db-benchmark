"""
Test Qdrant's indexing time after removal of specified % of points.


This script will:

- Create a Qdrant collection, and make initial upload of all vectors.
- Remove the specified number of points from the collection and measure the time it takes to re-index the collection.

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
DATASET_NAME = os.getenv("DATASET_NAME", "dbpedia_openai_100K")
DATA_DIR = Path(__file__).parent / "data" / DATASET_NAME
OUTPUT_FILENAME = os.getenv("OUTPUT_FILENAME", "output.json")
POINTS_PERCENTAGE = int(os.getenv("POINTS_PERCENTAGE", 1))

VECTORS_FILE = DATA_DIR / "vectors.npy"

TEST_DATA_FILE = DATA_DIR / "tests.jsonl"

TOTAL_VECTORS = 100_000


def read_test_data(limit: int = 1000):
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
    with open(TEST_DATA_FILE, "r") as f:
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
                deleted_threshold=0.001, vacuum_min_vector_number=100
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
    vectors = np.load(VECTORS_FILE)

    benchmark = QdrantBenchmark("http://localhost:6333")
    benchmark.initial_upload(vectors)
    benchmark.wait_ready()

    # Calculate number of points to delete based on percentage
    num_points_to_delete = int(TOTAL_VECTORS * POINTS_PERCENTAGE / 100)
    # Select points to delete
    points_to_delete = random.sample(range(TOTAL_VECTORS), num_points_to_delete)
    benchmark.delete_points(points_to_delete)

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
