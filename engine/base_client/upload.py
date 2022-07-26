import time
from multiprocessing import get_context

from engine.base_client.utils import JSONFileConverter, iter_batches


class BaseUploader:
    MP_CONTEXT = None
    client = None
    collection = None

    @classmethod
    def init_client(cls, url, collection_name):
        cls.client = ...
        cls.collection = ...

    @classmethod
    def upload(cls, url, collection_name, filename, batch_size, parallel):
        latencies = []

        with open(filename, "r") as fp:
            json_fp = JSONFileConverter(fp)

            if parallel == 1:
                cls.init_client(url, collection_name)
                for ids, batch in iter_batches(json_fp, batch_size):
                    latencies.append(cls.upload_batch(batch, ids))

            else:
                ctx = get_context(cls.MP_CONTEXT)
                with ctx.Pool(
                    processes=int(parallel),
                    initializer=cls.init_client,
                    initargs=(
                        url,
                        collection_name,
                    ),
                ) as pool:
                    latencies = pool.imap(
                        cls._upload_batch, iter_batches(json_fp, batch_size)
                    )

        return latencies

    @classmethod
    def _upload_batch(cls, batch, ids) -> float:
        start = time.perf_counter()
        cls.upload_batch(batch, ids)
        return time.perf_counter() - start

    @classmethod
    def upload_batch(cls, batch, ids) -> float:
        raise NotImplementedError()
