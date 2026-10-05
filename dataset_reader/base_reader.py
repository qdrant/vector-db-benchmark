from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class SparseVector:
    indices: list[int]
    values: list[float]


@dataclass
class Record:
    id: int
    vector: list[float] | None
    sparse_vector: SparseVector | None
    metadata: dict | None


@dataclass
class Query:
    vector: list[float] | None
    sparse_vector: SparseVector | None
    meta_conditions: dict | None
    expected_result: list[int] | None
    expected_scores: list[float] | None = None


class BaseReader:
    def read_data(self) -> Iterator[Record]:
        raise NotImplementedError()

    def read_queries(self) -> Iterator[Query]:
        raise NotImplementedError()

    def prefetch(self, vector, *items) -> list:
        raise NotImplementedError()
