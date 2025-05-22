"""
Test Qdrant's accuracy in scenarios of continuous updates of real data.


This script will:

- Create a Qdrant collection, and make initial upload of all available vectors from `data/dataset1`
- Measure the accuracy of the search
- Start replacing vectors of collection by removing points and replacing them with new ones from `data/dataset2`
- Once finished, measure the accuracy of the search

"""

import json
import os
import random
import time
from pathlib import Path

import numpy as np
import tqdm
from qdrant_client import QdrantClient, models

QDRANT_COLLECTION_NAME = "Benchmark"

DATASET_DIM = int(os.getenv("DATASET_DIM", 512))
DATASET_NAME = os.getenv("DATASET_NAME", "laion-small-clip-no-filters-1")
DATASET_NAME_2 = os.getenv("DATASET_NAME_2", "laion-small-clip-no-filters-2")
DATA_DIR = Path(__file__).parent / "data" / DATASET_NAME
DATA_DIR_2 = Path(__file__).parent / "data" / DATASET_NAME_2

VECTORS_FILE_2 = DATA_DIR_2 / "vectors.npy"
VECTORS_FILE_1 = DATA_DIR / "vectors.npy"

TEST_DATA_FILE_2 = DATA_DIR_2 / "tests.jsonl"
TEST_DATA_FILE_1 = DATA_DIR / "tests.jsonl"

TOTAL_VECTORS = 100_000
BATCH_SIZE = 500


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
                deleted_threshold=0.001,
                vacuum_min_vector_number=100,
                default_segment_number=1,
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

    def validate_test_data(self, file: Path) -> float:
        total_results = 0
        matched_results = 0
        for test in tqdm.tqdm(read_test_data(file), desc="Validating test data"):
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
        wait_time = 0.1
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

    vectors_1 = np.load(VECTORS_FILE_1)
    vectors_2 = np.load(VECTORS_FILE_2)

    benchmark = QdrantBenchmark("http://localhost:6333")
    benchmark.initial_upload(vectors_1)

    print(
        "Initial precision dataset1: ", benchmark.validate_test_data(TEST_DATA_FILE_1)
    )

    points_to_migrate = list(range(TOTAL_VECTORS))

    random.shuffle(points_to_migrate)

    total_indexing_time = 0
    for i in tqdm.tqdm(range(0, len(points_to_migrate), BATCH_SIZE), desc="Iterating"):
        batch = points_to_migrate[i : i + BATCH_SIZE]

        benchmark.delete_points(set(batch))

        benchmark.upload_points(vectors_2, batch)

        total_indexing_time += benchmark.wait_ready()

    print(f"Indexing: {total_indexing_time}")
    print("Precision dataset2: ", benchmark.validate_test_data(TEST_DATA_FILE_2))


if __name__ == "__main__":
    main()
