import functools
import time
from multiprocessing import get_context
from typing import Iterable, List, Optional, Tuple

import numpy as np
import tqdm
import os

from dataset_reader.base_reader import Query
from swagger_client.models.import_queries_request import ImportQueriesRequest


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
    def search_one(
        cls, vector: List[float], meta_conditions, top: Optional[int]
    ) -> List[Tuple[int, float]]:
        raise NotImplementedError()

    @classmethod
    def _search_one(cls, query, top: Optional[int] = None):
        
        # if cls.__name__ == "GSISearcher":
        #     from engine.clients.gsi.config import GSI_DEFAULT_QUERY_PATH
            
        #     idx = os.environ["id"]
        #     qpath = GSI_DEFAULT_QUERY_PATH + idx + ".npy"
        #     if os.path.exists(qpath):
        #         os.remove(qpath)
        #     vec = np.array(query.vector)
        #     vec = vec.reshape((1, len(vec)))
        #     np.save(qpath, vec)
        
        if top is None:
            top = (
                len(query.expected_result)
                if query.expected_result is not None and len(query.expected_result) > 0
                else DEFAULT_TOP
            )        
        idx = os.environ['id']
        
        start = time.perf_counter()
        search_res = cls.search_one(query.vector, query.meta_conditions, top)
        end = time.perf_counter()
        
        os.environ["id"] = str(int(idx) + 1)

        precision = 1.0
        if query.expected_result:
            ids = set(x[0] for x in search_res)
            precision = len(ids.intersection(query.expected_result[:top])) / top

        return precision, end - start

    def search_all(
        self,
        distance,
        queries: Iterable[Query],
    ):
        parallel = self.search_params.pop("parallel", 1)
        top = self.search_params.pop("top", None)

        # setup_search may require initialized client
        self.init_client(
            self.host, distance, self.connection_params, self.search_params
        )
        self.setup_search()

        search_one = functools.partial(self.__class__._search_one, top=top)

        if parallel == 1:
            start = time.perf_counter()
            precisions, latencies = list(
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
                precisions, latencies = list(
                    zip(*pool.imap_unordered(search_one, iterable=tqdm.tqdm(queries)))
                )

        total_time = time.perf_counter() - start
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
        }

    def setup_search(self):
        pass

    def post_search(self):
        pass
