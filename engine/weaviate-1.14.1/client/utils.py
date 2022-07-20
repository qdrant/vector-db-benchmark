import json
import uuid
from typing import Iterable, Any, TextIO, Union


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
    i = 0
    for line in fp:
        batch.append({"id": uuid.UUID(int=i).hex, "vector": line, "data": {}})
        if len(batch) >= n:
            yield batch
            batch = []
    if len(batch) > 0:
        yield batch
