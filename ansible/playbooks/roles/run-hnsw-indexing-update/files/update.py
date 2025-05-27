"""
Test Qdrant's accuracy in scenario of continuous updates of real data.


This script will:

- Create a Qdrant collection, and make initial upload of all available vectors.
- Randomly delete 1000 vectors from the collection, while keeping track of what is currently deleted
- Measure baseline accuracy here

- Repeatedly:
    - Upload 500 of the deleted vectors back
    - Pick another random 500 vectors, and delete them
    - Measure the accuracy of the search

"""

import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import tqdm
from qdrant_client import QdrantClient, models

QDRANT_COLLECTION_NAME = "benchmark"
DATASET_DIM = int(os.getenv("DATASET_DIM", 1536))
DATASET_NAME = os.getenv("DATASET_NAME", "dbpedia_openai_100K")
DATA_DIR = Path(__file__).parent / "data" / DATASET_NAME
OUTPUT_FILENAME = os.getenv("OUTPUT_FILENAME", "output.json")

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

    def upload_points(self, vectors: np.ndarray, ids: list[int]):
        points = [
            models.PointStruct(id=idx, vector=vectors[idx].tolist()) for idx in ids
        ]

        self.client.upsert(
            collection_name=QDRANT_COLLECTION_NAME,
            points=points,
        )

    def validate_test_data(self) -> float:
        total_results = 0
        matched_results = 0
        for test in tqdm.tqdm(read_test_data(), desc="Validating test data"):
            query = test["query"]
            closest_ids = set(test["closest_ids"])

            results = self.client.query_points(
                collection_name=QDRANT_COLLECTION_NAME,
                query=query,
                limit=len(closest_ids),
            )

            results_idx = set(obj.id for obj in results.points)

            matched_results += len(closest_ids & results_idx)
            total_results += len(closest_ids)

        return matched_results / total_results

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

    deleted_points = set()

    benchmark = QdrantBenchmark("http://localhost:6333")
    benchmark.initial_upload(vectors)

    benchmark.wait_ready()

    initial_precision = benchmark.validate_test_data()
    print("Initial precision: ", initial_precision)
    result["initial_precision"] = initial_precision

    # Delete 1000 random points
    points_to_delete = random.sample(range(TOTAL_VECTORS), 1000)
    points_rest = set(range(TOTAL_VECTORS)) - set(points_to_delete)

    benchmark.delete_points(points_to_delete)

    deleted_points.update(points_to_delete)

    benchmark.wait_ready()

    precision_after_deletion = benchmark.validate_test_data()
    print("Precision after deletion: ", precision_after_deletion)
    result["precision_before_iteration"] = precision_after_deletion

    total_indexing_time = 0
    for _ in tqdm.tqdm(range(100), desc="Iterating"):
        # Select 500 points to upload, from the points that were already deleted
        points_to_upload = random.sample(list(deleted_points), 500)

        benchmark.upload_points(vectors, points_to_upload)

        # Remove the points that were uploaded from the deleted points
        deleted_points.difference_update(points_to_upload)

        # Select 500 points to delete, from the points that haven't been deleted yet
        points_to_delete = random.sample(list(points_rest), 500)
        points_rest = set(points_rest) - set(points_to_delete)

        benchmark.delete_points(points_to_delete)

        deleted_points.update(points_to_delete)

        total_indexing_time += benchmark.wait_ready()

    print(f"Indexing: {total_indexing_time}")
    result["indexing_total_time_s"] = total_indexing_time

    precision_after_iteration = benchmark.validate_test_data()
    print(f"Iteration 99, Precision: {precision_after_iteration}")
    result["precision_after_iteration"] = precision_after_iteration

    store_to_file(result)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    main()

    sys.stdout.flush()
    sys.stderr.flush()
