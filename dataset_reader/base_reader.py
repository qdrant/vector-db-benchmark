from dataclasses import dataclass
from typing import Iterator, List, Optional


@dataclass
class Record:
    id: int
    vector: List[float]
    metadata: Optional[dict]


@dataclass
class Query:
    vector: List[float]
    meta_conditions: Optional[dict]
    expected_result: Optional[List[int]]
    expected_scores: Optional[List[float]] = None


class BaseReader:
    def read_data(self) -> Iterator[Record]:
        raise NotImplementedError()

    def read_queries(self) -> Iterator[Query]:
        raise NotImplementedError()
