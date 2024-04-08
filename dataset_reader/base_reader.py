from dataclasses import dataclass
from typing import Iterator, List, Optional

import numpy as np


@dataclass
class SparseVector:
    indices: np.array
    values: np.array


@dataclass
class Record:
    id: int
    vector: Optional[List[float]]
    sparse_vector: Optional[SparseVector]
    metadata: Optional[dict]

    def __post__init__(self):
        dense_vector = self.vector is not None
        sparse_vector = self.sparse_vector is not None

        # Only one of them can be provided but not both.
        if (dense_vector or sparse_vector) and not (dense_vector and sparse_vector):
            raise ValueError(
                "Only one of vector or sparse_vector must be provided for Record"
            )


@dataclass
class Query:
    vector: Optional[List[float]]
    sparse_vector: Optional[SparseVector]
    meta_conditions: Optional[dict]
    expected_result: Optional[List[int]]
    expected_scores: Optional[List[float]] = None

    def __post__init__(self):
        dense_vector = self.vector is not None
        sparse_vector = self.sparse_vector is not None

        # Only one of them can be provided but not both.
        if (dense_vector or sparse_vector) and not (dense_vector and sparse_vector):
            raise ValueError(
                "Only one of vector or sparse_vector must be provided for Query"
            )


class BaseReader:
    def read_data(self) -> Iterator[Record]:
        raise NotImplementedError()

    def read_queries(self) -> Iterator[Query]:
        raise NotImplementedError()

    def prefetch(self, vector, *items) -> List:
        raise NotImplementedError()
