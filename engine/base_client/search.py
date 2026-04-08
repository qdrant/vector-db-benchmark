import functools
import time
from multiprocessing import get_context
from typing import Iterable, List, Optional, Tuple

import numpy as np
import tqdm

from dataset_reader.base_reader import Query

DEFAULT_TOP = 10
RECALL_AT_K_VALUES = [1, 2, 4, 8, 16, 32, 64]


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

        precision = 1.0
        recall_at_1_at_k = {}
        if query.expected_result:
            ids = set(x[0] for x in search_res)
            precision = len(ids.intersection(query.expected_result[:top])) / top

            # Compute recall@1@k: is the true nearest neighbor in the top-k results?
            true_nn = query.expected_result[0]
            result_ids = [x[0] for x in search_res]
            try:
                nn_pos = result_ids.index(true_nn) + 1  # 1-based position
            except ValueError:
                nn_pos = float("inf")  # not found at all
            for k in RECALL_AT_K_VALUES:
                if k <= len(result_ids):
                    recall_at_1_at_k[k] = 1.0 if nn_pos <= k else 0.0

        return precision, end - start, recall_at_1_at_k

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
            precisions, latencies, recall_at_1_at_k_list = list(
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
                precisions, latencies, recall_at_1_at_k_list = list(
                    zip(*pool.imap_unordered(search_one, iterable=tqdm.tqdm(queries)))
                )

        total_time = time.perf_counter() - start

        self.__class__.delete_client()

        # Aggregate recall@1@k across all queries
        mean_recall_at_1_at_k = {}
        for k in RECALL_AT_K_VALUES:
            values = [r[k] for r in recall_at_1_at_k_list if k in r]
            if values:
                mean_recall_at_1_at_k[k] = float(np.mean(values))

        return {
            "total_time": total_time,
            "mean_time": np.mean(latencies),
            "mean_precisions": np.mean(precisions),
            "std_time": np.std(latencies),
            "min_time": np.min(latencies),
            "max_time": np.max(latencies),
            "rps": len(latencies) / total_time,
            "p95_time": np.percentile(latencies, 95),
            "p99_time": np.percentile(latencies, 99),
            "precisions": precisions,
            "latencies": latencies,
            "recall_at_1_at_k": mean_recall_at_1_at_k,
        }

    def setup_search(self):
        pass

    def post_search(self):
        pass

    @classmethod
    def delete_client(cls):
        pass
