import json
import tarfile
from io import BytesIO
from typing import Iterator

import numpy as np

from dataset_reader.base_reader import BaseReader, Query, Record


class TarCompoundReader(BaseReader):
    """
    A reader created specifically to read the format used in
    https://github.com/qdrant/ann-filtering-benchmark-datasets, in which vectors
    and their metadata are stored in separate files.
    """

    def __init__(self, path, normalize=False):
        self.path = path
        self.normalize = normalize

    def read_data(self) -> Iterator[Record]:
        with tarfile.open(self.path, encoding="utf-8") as tf:
            # Numpy array has to be loaded through BytesIO before using .load on
            # tar extracted files: https://github.com/numpy/numpy/issues/7989
            vectors_fp = tf.extractfile("./vectors.npy")
            buffer = BytesIO(vectors_fp.read())
            vectors = np.load(buffer)

            payloads_fp = tf.extractfile("./payloads.jsonl")
            for idx, row in enumerate(payloads_fp):
                vector = vectors[idx]
                if self.normalize:
                    vector /= np.linalg.norm(vector)
                yield Record(
                    id=idx,
                    vector=vector.tolist(),
                    metadata=json.loads(row),
                )

    def read_queries(self) -> Iterator[Query]:
        with tarfile.open(self.path, encoding="utf-8") as tf:
            payloads_fp = tf.extractfile("./tests.jsonl")
            for idx, row in enumerate(payloads_fp):
                row_json = json.loads(row)
                vector = np.array(row_json["query"])
                if self.normalize:
                    vector /= np.linalg.norm(vector)
                yield Query(
                    vector=vector.tolist(),
                    meta_conditions=row_json["conditions"],
                    expected_result=row_json["closest_ids"],
                    expected_scores=row_json["closest_scores"],
                )
