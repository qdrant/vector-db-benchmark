from typing import List, Optional, Tuple
import hnswlib
import os
from engine.base_client.search import BaseSearcher
from engine.clients.hnswlib_bench.config import DEFAULT_INDEX_PATH

class HNSWLibSearcher(BaseSearcher):
    search_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.search_params = search_params
        # load index
        dim = int(os.getenv("DIM"))
        cls.index = hnswlib.Index(space=distance, dim=dim)
        cls.index.load_index(DEFAULT_INDEX_PATH)
        cls.index.set_ef(search_params['vectorIndexConfig']['ef'])

    @classmethod
    def search_one(cls, vector: List[float], meta_conditions, top) -> List[Tuple[int, float]]:
        labels, distances = cls.index.knn_query(vector, k=top)
        id_score_pairs: List[Tuple[int, float]] = []
        for ind, dist in zip(labels[0], distances[0]):
            id_score_pairs.append((ind, dist))
        return id_score_pairs