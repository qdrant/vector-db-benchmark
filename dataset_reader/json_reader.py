from pathlib import Path
from typing import Iterator, List, Optional

import json

from dataset_reader.base_reader import BaseReader, Record, Query


VECTORS_FILE = 'vectors.jsonl'
PAYLOADS_FILE = 'payloads.jsonl'
QUERIES_FILE = 'queries.jsonl'
NEIGHBOURS_FILE = 'neighbours.jsonl'


class JSONReader(BaseReader):
    def __init__(self, path: Path):
        self.path = path

    def read_payloads(self) -> Iterator[dict]:
        if not (self.path / PAYLOADS_FILE).exists():
            while True:
                yield {}
        with open(self.path / PAYLOADS_FILE, "r") as json_fp:
            for json_line in json_fp:
                line = json.loads(json_line)
                yield line

    def read_vectors(self) -> Iterator[List[float]]:
        with open(self.path / VECTORS_FILE, "r") as json_fp:
            for json_line in json_fp:
                line = json.loads(json_line)
                yield line

    def read_neighbours(self) -> Iterator[Optional[List[int]]]:
        if not (self.path / NEIGHBOURS_FILE).exists():
            while True:
                yield None

        with open(self.path / NEIGHBOURS_FILE, "r") as json_fp:
            for json_line in json_fp:
                line = json.loads(json_line)
                yield line

    def read_query_vectors(self) -> Iterator[List[float]]:
        with open(self.path / QUERIES_FILE, "r") as json_fp:
            for json_line in json_fp:
                line = json.loads(json_line)
                yield line

    def read_queries(self) -> Iterator[Query]:
        for idx, (vector, neighbours) in enumerate(zip(self.read_query_vectors(), self.read_neighbours())):
            # ToDo: add meta_conditions
            yield Query(vector=vector, meta_conditions=None, expected_result=neighbours)

    def read_data(self) -> Iterator[Record]:
        for idx, (vector, payload) in enumerate(zip(self.read_vectors(), self.read_payloads())):
            yield Record(id=idx, vector=vector, metadata=payload)


if __name__ == "__main__":
    from benchmark import DATASETS_DIR

    test_path = DATASETS_DIR / "random-100"
    record = next(JSONReader(test_path).read_data())
    print(record, end="\n\n")

    query = next(JSONReader(test_path).read_queries())
    print(query)
