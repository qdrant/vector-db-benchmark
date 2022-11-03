from typing import List, Tuple

import numpy as np
import redis
from redis.commands.search.query import Query

from engine.base_client.search import BaseSearcher
from engine.clients.redis.config import REDIS_PORT
from engine.clients.redis.parser import RedisConditionParser


class RedisSearcher(BaseSearcher):
    search_params = {}
    client = None
    parser = RedisConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.client = redis.Redis(host=host, port=REDIS_PORT, db=0)
        cls.search_params = search_params

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        prefilter_condition, params = cls.parser.parse(meta_conditions)
        q = (
            Query(
                f"{prefilter_condition}=>[KNN $K @vector $vec_param EF_RUNTIME $EF AS vector_score]"
            )
            .sort_by("vector_score", asc=False)
            .paging(0, top)
            .return_fields("vector_score")
            .dialect(2)
        )
        params_dict = {
            "vec_param": np.array(vector).astype(np.float32).tobytes(),
            "K": top,
            "EF": cls.search_params["search_params"]["ef"],
            **params,
        }

        results = cls.client.ft().search(q, query_params=params_dict)

        return [(int(result.id), float(result.vector_score)) for result in results.docs]
