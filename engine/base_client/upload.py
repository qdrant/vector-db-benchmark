import time
from multiprocessing import get_context
from typing import List, Optional, Iterable

from dataset_reader.base_reader import Record
from engine.base_client.utils import iter_batches


class BaseUploader:
    MP_CONTEXT = None
    client = None

    @classmethod
    def init_client(cls, host, connection_params: dict):
        cls.client = ...
        raise NotImplementedError()

    @classmethod
    def upload(
        cls,
        url: str,
        records: Iterable[Record],
        batch_size: int,
        parallel: int,
        connection_params: dict,
    ) -> List[float]:
        latencies = []

        if parallel == 1:
            cls.init_client(url, connection_params)
            for ids, vectors, metadata in iter_batches(records, batch_size):
                latencies.append(cls.upload_batch(ids, vectors, metadata))

        else:
            ctx = get_context(cls.MP_CONTEXT)
            with ctx.Pool(
                processes=int(parallel),
                initializer=cls.init_client,
                initargs=(url, connection_params),
            ) as pool:
                latencies = pool.imap(
                    cls._upload_batch, iter_batches(records, batch_size)
                )

        return latencies

    @classmethod
    def _upload_batch(
        cls, ids: List[int], vectors: List[list], metadata: List[Optional[dict]]
    ) -> float:
        start = time.perf_counter()
        cls.upload_batch(ids, vectors, metadata)
        return time.perf_counter() - start

    @classmethod
    def upload_batch(
        cls, ids: List[int], vectors: List[list], metadata: List[Optional[dict]]
    ):
        raise NotImplementedError()
