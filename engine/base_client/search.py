import time
import functools
from multiprocessing import get_context
from typing import List, Tuple, Iterable, Optional

import numpy as np

from dataset_reader.base_reader import Query


DEFAULT_TOP = 10


class BaseSearcher:
    MP_CONTEXT = None

    def __init__(self, host, connection_params, search_params):
        self.host = host
        self.connection_params = connection_params
        self.search_params = search_params

    @classmethod
    def init_client(cls, host: str, connection_params: dict, search_params: dict):
        raise NotImplementedError()

    @classmethod
    def search_one(
        cls, vector: List[float], meta_conditions, top: Optional[int]
    ) -> List[Tuple[int, float]]:
        raise NotImplementedError()

    @classmethod
    def _search_one(cls, query, top: Optional[int] = None):
        if top is None:
            top = (
                len(query.expected_result) if query.expected_result is not None else DEFAULT_TOP
            )

        start = time.perf_counter()
        search_res = cls.search_one(query.vector, query.meta_conditions, top)
        end = time.perf_counter()

        precision = 1.0
        if query.expected_result is not None:
            ids = set(x[0] for x in search_res)
            precision = len(ids.intersection(query.expected_result[:top])) / top

        return precision, end - start

    def search_all(
        self, queries: Iterable[Query],
    ):
        start = time.perf_counter()
        parallel = self.search_params.pop("parallel", 1)
        top = self.search_params.pop("top", None)

        self.setup_search()

        search_one = functools.partial(self.__class__._search_one, top=top)

        if parallel == 1:
            self.init_client(self.host, self.connection_params, self.search_params)
            precisions, latencies = list(zip(*[search_one(query) for query in queries]))
        else:
            ctx = get_context(self.MP_CONTEXT)

            with ctx.Pool(
                processes=parallel,
                initializer=self.__class__.init_client,
                initargs=(self.host, self.connection_params, self.search_params),
            ) as pool:
                precisions, latencies = list(
                    zip(*pool.imap_unordered(search_one, iterable=queries))
                )

        total_time = time.perf_counter() - start
        return {
            "total_time": total_time,
            "mean_time": np.std(latencies),
            "mean_precisions": np.mean(precisions),
            "std_time": np.mean(latencies),
            "min_time": np.min(latencies),
            "max_time": np.max(latencies),
            "rps": len(latencies) / total_time,
            "p95_time": np.percentile(latencies, 95),
            "p99_time": np.percentile(latencies, 99),
            "precisions": precisions,
            "latencies": latencies,
        }

    def set_process_start_method(self, start_method):
        self.MP_CONTEXT = start_method

    def setup_search(self):
        pass
