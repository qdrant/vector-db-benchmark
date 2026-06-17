import functools
import time
from multiprocessing import get_context
from typing import Iterable, List, Optional, Tuple

import numpy as np
import tqdm

from dataset_reader.base_reader import Query

DEFAULT_TOP = 10


class BaseSearcher:
    MP_CONTEXT = None

    def __init__(self, host, connection_params, search_params):
        self.host = host
        self.connection_params = connection_params
        self.search_params = search_params

    @classmethod
    def init_client(
        cls, host: str, distance, connection_params: dict, search_params: dict
    ):
        raise NotImplementedError()

    @classmethod
    def get_mp_start_method(cls):
        return None

    @classmethod
    def search_one(cls, query: Query, top: Optional[int]) -> List[Tuple[int, float]]:
        raise NotImplementedError()

    @classmethod
    def server_latency(cls) -> Optional[float]:
        """Return server-side processing time (seconds) for the last search_one call.

        Override in engines that expose server-side timing (e.g. Qdrant REST).
        Returns None by default (not supported).
        """
        return None

    @classmethod
    def _search_one(cls, query: Query, top: Optional[int] = None):
        if top is None:
            top = (
                len(query.expected_result)
                if query.expected_result is not None and len(query.expected_result) > 0
                else DEFAULT_TOP
            )

        start = time.perf_counter()
        search_res = cls.search_one(query, top)
        end = time.perf_counter()
        server_lat = cls.server_latency()

        precision = 1.0
        if query.expected_result:
            ids = set(x[0] for x in search_res)
            precision = len(ids.intersection(query.expected_result[:top])) / top

        return precision, end - start, server_lat

    def search_all(
        self,
        distance,
        queries: Iterable[Query],
    ):
        parallel = self.search_params.get("parallel", 1)
        top = self.search_params.get("top", None)

        # setup_search may require initialized client
        self.init_client(
            self.host, distance, self.connection_params, self.search_params
        )
        self.setup_search()

        search_one = functools.partial(self.__class__._search_one, top=top)

        if parallel == 1:
            start = time.perf_counter()
            precisions, latencies, server_latencies = list(
                zip(*[search_one(query) for query in tqdm.tqdm(queries)])
            )
        else:
            ctx = get_context(self.get_mp_start_method())

            with ctx.Pool(
                processes=parallel,
                initializer=self.__class__.init_client,
                initargs=(
                    self.host,
                    distance,
                    self.connection_params,
                    self.search_params,
                ),
            ) as pool:
                if parallel > 10:
                    time.sleep(15)  # Wait for all processes to start
                start = time.perf_counter()
                precisions, latencies, server_latencies = list(
                    zip(*pool.imap_unordered(search_one, iterable=tqdm.tqdm(queries)))
                )

        total_time = time.perf_counter() - start

        self.post_search()
        self.__class__.delete_client()

        results = {
            "total_time": total_time,
            "mean_time": np.mean(latencies),
            "mean_precisions": np.mean(precisions),
            "std_time": np.std(latencies),
            "min_time": np.min(latencies),
            "max_time": np.max(latencies),
            "rps": len(latencies) / total_time,
            "p1_time": np.percentile(latencies, 1),
            "p10_time": np.percentile(latencies, 10),
            "p25_time": np.percentile(latencies, 25),
            "p95_time": np.percentile(latencies, 95),
            "p99_time": np.percentile(latencies, 99),
            "precisions": precisions,
            "latencies": latencies,
        }

        actual_server_lats = [l for l in server_latencies if l is not None]
        if actual_server_lats:
            results["mean_server_time"] = np.mean(actual_server_lats)
            results["p95_server_time"] = np.percentile(actual_server_lats, 95)
            results["p99_server_time"] = np.percentile(actual_server_lats, 99)
            results["server_latencies"] = server_latencies

        return results

    def setup_search(self):
        pass

    def post_search(self):
        pass

    @classmethod
    def delete_client(cls):
        pass
