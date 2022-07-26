import json
from typing import Any, Iterable, TextIO, Union


class FileConverter:
    def __init__(self, fp: TextIO):
        self._fp = fp

    def __iter__(self):
        raise NotImplementedError()


class JSONFileConverter(FileConverter):
    def __iter__(self):
        for line in self._fp:
            yield json.loads(line)


def iter_batches(fp: Union[FileConverter, TextIO], n: int) -> Iterable[Any]:
    batch = []
    indices = []
    for ind, line in enumerate(fp):
        indices.append(ind)
        batch.append(line)
        if len(batch) >= n:
            yield [indices, batch]
            batch = []
            indices = []
    if len(indices) > 0:
        yield [indices, batch]
