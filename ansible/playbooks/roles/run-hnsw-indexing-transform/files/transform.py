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
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import tqdm
from qdrant_client import QdrantClient, models

QDRANT_COLLECTION_NAME = "benchmark"
OUTPUT_FILENAME = os.getenv("OUTPUT_FILENAME", "output.json")
DATASET_DIM = int(os.getenv("DATASET_DIM", 512))
DATASET_NAME = os.getenv("DATASET_NAME", "laion-small-clip-no-filters-1")
DATASET_NAME_2 = os.getenv("DATASET_NAME_2", "laion-small-clip-no-filters-2")
DATA_DIR = Path(__file__).parent / "data" / DATASET_NAME
DATA_DIR_2 = Path(__file__).parent / "data" / DATASET_NAME_2

VECTORS_FILE_2 = DATA_DIR_2 / "vectors.npy"
VECTORS_FILE_1 = DATA_DIR / "vectors.npy"

TEST_DATA_FILE_2 = DATA_DIR_2 / "tests.jsonl"
TEST_DATA_FILE_1 = DATA_DIR / "tests.jsonl"

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

    initial_precision = benchmark.validate_test_data(TEST_DATA_FILE_1)
    print("Precision dataset1: ", initial_precision)
    result["initial_precision"] = initial_precision
    result["precision_before_iteration"] = initial_precision

    points_to_migrate = list(range(len(vectors_1)))

    random.shuffle(points_to_migrate)

    total_indexing_time = 0
    for i in tqdm.tqdm(range(0, len(points_to_migrate), BATCH_SIZE), desc="Iterating"):
        batch = points_to_migrate[i : i + BATCH_SIZE]

        benchmark.delete_points(set(batch))

        benchmark.upload_points(vectors_2, batch)

        total_indexing_time += benchmark.wait_ready()

    print(f"Indexing: {total_indexing_time}")
    result["indexing_total_time_s"] = total_indexing_time

    precision_after_iteration = benchmark.validate_test_data(TEST_DATA_FILE_2)
    print(f"Precision dataset2: {precision_after_iteration}")
    result["precision_after_iteration"] = precision_after_iteration

    store_to_file(result)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    main()

    sys.stdout.flush()
    sys.stderr.flush()
