import time
from multiprocessing import get_context
from typing import List, Tuple, Iterable

from dataset_reader.base_reader import Query


class BaseSearcher:
    MP_CONTEXT = None

    @classmethod
    def init_client(cls, host, connection_params, search_params):
        cls.search_params = search_params
        raise NotImplementedError()

    @classmethod
    def search_one(cls, vector, meta_conditions) -> List[Tuple[int, float]]:
        raise NotImplementedError()

    @classmethod
    def _search_one(cls, query):
        start = time.perf_counter()
        search_res = cls.search_one(query.vector, query.meta_conditions)
        end = time.perf_counter()

        precision = 1.0
        if query.expected_result is not None:
            top = len(query.expected_result)
            ids = set(x[0] for x in search_res)
            precision = len(ids.intersection(query.expected_result)) / top

        return precision, end - start

    @classmethod
    def search_all(
        cls, url, connection_params, search_params, queries: Iterable[Query], parallel,
    ):
        cls.init_client(url, connection_params, search_params)

        if parallel == 1:
            precisions, latencies = list(
                zip([cls._search_one(query) for query in queries])
            )
        else:
            ctx = get_context(cls.MP_CONTEXT)

            with ctx.Pool(
                processes=parallel,
                initializer=cls.init_client,
                initargs=(url, connection_params,),
            ) as pool:
                precisions, latencies = list(
                    zip(*pool.imap_unordered(cls._search_one, iterable=queries))
                )

        return precisions, latencies

    @classmethod
    def set_process_start_method(cls, start_method):
        cls.MP_CONTEXT = start_method
