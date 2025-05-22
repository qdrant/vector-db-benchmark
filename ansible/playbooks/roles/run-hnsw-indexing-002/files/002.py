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

import numpy as np
import random
import time
from pathlib import Path
import tqdm

from qdrant_client import QdrantClient, models


QDRANT_COLLECTION_NAME = "benchmark"
DATASET_DIM = int(os.getenv("DATASET_DIM", 1536))
DATASET_NAME = os.getenv("DATASET_NAME", "dbpedia_openai_100K")
DATA_DIR = Path(__file__).parent / "data" / DATASET_NAME

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
                deleted_threshold=0.001,
                vacuum_min_vector_number=100
            )
        )

    def initial_upload(self, vectors: np.ndarray):
        self.client.upload_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors=vectors,
            ids=range(len(vectors)),
        )

    def upload_points(self, vectors: np.ndarray, ids: list[int]):
        points =[models.PointStruct(id=idx, vector=vectors[idx].tolist()) for idx in ids]

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

    def wait_ready(self):
        wait_time = 0.2
        total = 0
        while True:
            time.sleep(wait_time)
            total += wait_time
            collection_info = self.client.get_collection(QDRANT_COLLECTION_NAME)
            if collection_info.status != models.CollectionStatus.GREEN:
                continue
            time.sleep(wait_time)
            collection_info = self.client.get_collection(QDRANT_COLLECTION_NAME)
            if collection_info.status == models.CollectionStatus.GREEN:
                break
        return total

    def __del__(self):
        self.client.close()


def main():

    vectors = np.load(VECTORS_FILE)

    deleted_points = set()

    benchmark = QdrantBenchmark("http://localhost:6333")
    benchmark.initial_upload(vectors)

    print("Initial precision: ", benchmark.validate_test_data())

    # Delete 1000 random points
    points_to_delete = random.sample(range(TOTAL_VECTORS), 1000)

    benchmark.delete_points(points_to_delete)

    deleted_points.update(points_to_delete)

    benchmark.wait_ready()

    print("Precision after deletion: ", benchmark.validate_test_data())

    total_indexing_time = 0
    for _ in tqdm.tqdm(range(100), desc="Iterating"):
        # Select 500 points to upload, from the points that was already deleted
        points_to_upload = random.sample(list(deleted_points), 500)

        benchmark.upload_points(vectors, points_to_upload)

        # Remove the points that was uploaded from the deleted points
        deleted_points.difference_update(points_to_upload)

        # Select 500 points to delete, from the points that was not deleted yet
        points_to_delete = random.sample(range(TOTAL_VECTORS), 500)

        benchmark.delete_points(points_to_delete)

        deleted_points.update(points_to_delete)

        total_indexing_time += benchmark.wait_ready()

    print(f"Indexing: {total_indexing_time}")
    print(f"Iteration 99, Precision: {benchmark.validate_test_data()}")


if __name__ == "__main__":
    main()