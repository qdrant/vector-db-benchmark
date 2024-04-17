import json
from pathlib import Path
from typing import Iterator, List, Optional

import numpy as np

from dataset_reader.base_reader import BaseReader, Query, Record


class JSONReader(BaseReader):
    VECTORS_FILE = "vectors.jsonl"
    PAYLOADS_FILE = "payloads.jsonl"
    QUERIES_FILE = "queries.jsonl"
    NEIGHBOURS_FILE = "neighbours.jsonl"

    def __init__(self, path: Path, normalize=False):
        self.path = path
        self.normalize = normalize

    def read_payloads(self) -> Iterator[dict]:
        if not (self.path / self.PAYLOADS_FILE).exists():
            while True:
                yield {}
        with open(self.path / self.PAYLOADS_FILE, "r") as json_fp:
            for json_line in json_fp:
                line = json.loads(json_line)
                yield line

    def read_vectors(self) -> Iterator[List[float]]:
        with open(self.path / self.VECTORS_FILE, "r") as json_fp:
            for json_line in json_fp:
                vector = json.loads(json_line)
                if self.normalize:
                    vector = vector / np.linalg.norm(vector)
                yield vector

    def read_neighbours(self) -> Iterator[Optional[List[int]]]:
        if not (self.path / self.NEIGHBOURS_FILE).exists():
            while True:
                yield None

        with open(self.path / self.NEIGHBOURS_FILE, "r") as json_fp:
            for json_line in json_fp:
                line = json.loads(json_line)
                yield line

    def read_query_vectors(self) -> Iterator[List[float]]:
        with open(self.path / self.QUERIES_FILE, "r") as json_fp:
            for json_line in json_fp:
                vector = json.loads(json_line)
                if self.normalize:
                    vector /= np.linalg.norm(vector)
                yield vector

    def read_queries(self) -> Iterator[Query]:
        for idx, (vector, neighbours) in enumerate(
            zip(self.read_query_vectors(), self.read_neighbours())
        ):
            # ToDo: add meta_conditions

            yield Query(
                vector=vector,
                sparse_vector=None,
                meta_conditions=None,
                expected_result=neighbours,
            )

    def read_data(self) -> Iterator[Record]:
        for idx, (vector, payload) in enumerate(
            zip(self.read_vectors(), self.read_payloads())
        ):
            yield Record(id=idx, vector=vector, sparse_vector=None, metadata=payload)


if __name__ == "__main__":
    from benchmark import DATASETS_DIR

    test_path = DATASETS_DIR / "random-100"
    record = next(JSONReader(test_path).read_data())
    print(record, end="\n\n")

    query = next(JSONReader(test_path).read_queries())
    print(query)
