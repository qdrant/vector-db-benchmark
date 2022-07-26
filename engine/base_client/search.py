import time
import functools
from multiprocessing import get_context

from engine.base_client.utils import JSONFileConverter


class BaseSearcher:
    MP_CONTEXT = None
    client = None
    collection = None

    @classmethod
    def init_client(cls, url, collection_name, **kwargs):
        raise NotImplementedError()

    @classmethod
    def search_one(cls, vector, ef):
        raise NotImplementedError()

    @classmethod
    def _search_one(cls, vector, ef):
        start = time.perf_counter()
        cls.search_one(vector, ef)
        return time.perf_counter() - start

    @classmethod
    def search_all(cls, url, collection_name, filename, ef, parallel):
        cls.init_client(url, collection_name, ef=ef)

        with open(filename, 'r') as fp:
            json_fp = JSONFileConverter(fp)

            if parallel == 1:
                latencies = [cls._search_one(vector, ef) for vector in json_fp]
            else:
                search_one = functools.partial(cls._search_one, ef=ef)

                ctx = get_context(cls.MP_CONTEXT)
                with ctx.Pool(
                    processes=parallel,
                    initializer=cls.init_client,
                    initargs=(url, collection_name,),
                ) as pool:
                    latencies = list(pool.imap_unordered(search_one, iterable=json_fp))

        return latencies

    @classmethod
    def set_process_start_method(cls, start_method):
        cls.MP_CONTEXT = start_method
