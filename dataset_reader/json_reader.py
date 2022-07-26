from typing import Iterator

import json

from dataset_reader.base_reader import BaseReader, Record, Query


class JSONReader(BaseReader):
    def __init__(self, path):
        self.path = path

    def read_queries(self) -> Iterator[Query]:
        with open(self.path, "r") as json_fp:
            for json_line in json_fp:
                line = json.loads(json_line)
                yield Query(
                    vector=line, meta_conditions=None, expected_result=None,
                )

    def read_data(self) -> Iterator[Record]:
        with open(self.path, "r") as json_fp:
            for idx, json_line in enumerate(json_fp):
                line = json.loads(json_line)
                yield Record(id=idx, vector=line, metadata=None)


if __name__ == "__main__":
    import os
    from benchmark.settings import DATASET_DIR

    test_path = os.path.join(DATASET_DIR, "random-100", "vectors.jsonl")
    record = next(JSONReader(test_path).read_data())
    print(record, end="\n\n")

    query = next(JSONReader(test_path).read_queries())
    print(query)
