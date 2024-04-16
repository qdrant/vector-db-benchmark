from typing import Iterable, List

from dataset_reader.base_reader import Record


def iter_batches(records: Iterable[Record], n: int) -> Iterable[List[Record]]:
    batch = []

    for record in records:
        batch.append(record)

        if len(batch) >= n:
            yield batch
            batch = []
    if len(batch) > 0:
        yield batch
