from dataclasses import dataclass
from typing import Iterator, List, Optional


@dataclass
class SparseVector:
    indices: List[int]
    values: List[float]


@dataclass
class Record:
    id: int
    vector: Optional[List[float]]
    sparse_vector: Optional[SparseVector]
    metadata: Optional[dict]


@dataclass
class Query:
    vector: Optional[List[float]]
    sparse_vector: Optional[SparseVector]
    meta_conditions: Optional[dict]
    expected_result: Optional[List[int]]
    expected_scores: Optional[List[float]] = None


class BaseReader:
    def read_data(self) -> Iterator[Record]:
        raise NotImplementedError()

    def read_queries(self) -> Iterator[Query]:
        raise NotImplementedError()

    def prefetch(self, vector, *items) -> List:
        raise NotImplementedError()
