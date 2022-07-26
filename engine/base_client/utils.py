from typing import Any, Iterable

from dataset_reader.base_reader import Record


def iter_batches(records: Iterable[Record], n: int) -> Iterable[Any]:
    ids = []
    vectors = []
    metadata = []

    for record in records:
        ids.append(record.id)
        vectors.append(record.vector)
        metadata.append(record.metadata)

        if len(vectors) >= n:
            yield [ids, vectors, metadata]
            ids, vectors, metadata = [], [], []
    if len(ids) > 0:
        yield [ids, vectors, metadata]
