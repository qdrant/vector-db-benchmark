import random
from typing import List, Tuple

import numpy as np
from redis import Redis, RedisCluster
from redis.commands.search.query import Query as RedisQuery

from dataset_reader.base_reader import Query as DatasetQuery
from engine.base_client.search import BaseSearcher
from engine.clients.redis.config import (
    REDIS_AUTH,
    REDIS_CLUSTER,
    REDIS_PORT,
    REDIS_QUERY_TIMEOUT,
    REDIS_USER,
)
from engine.clients.redis.parser import RedisConditionParser


class RedisSearcher(BaseSearcher):
    search_params = {}
    client = None
    parser = RedisConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        redis_constructor = RedisCluster if REDIS_CLUSTER else Redis
        cls.client = redis_constructor(
            host=host, port=REDIS_PORT, password=REDIS_AUTH, username=REDIS_USER
        )
        cls.search_params = search_params
        cls.knn_conditions = "EF_RUNTIME $EF"
        cls._is_cluster = True if REDIS_CLUSTER else False
        # In the case of CLUSTER API enabled we randomly select the starting primary shard
        # when doing the client initialization to evenly distribute the load among the cluster
        cls.conns = [cls.client]
        if cls._is_cluster:
            cls.conns = [
                cls.client.get_redis_connection(node)
                for node in cls.client.get_primaries()
            ]
        cls._ft = cls.conns[random.randint(0, len(cls.conns)) - 1].ft()

    @classmethod
    def search_one(cls, query: DatasetQuery, top: int) -> List[Tuple[int, float]]:
        conditions = cls.parser.parse(query.meta_conditions)
        if conditions is None:
            prefilter_condition = "*"
            params = {}
        else:
            prefilter_condition, params = conditions

        q = (
            RedisQuery(
                f"{prefilter_condition}=>[KNN $K @vector $vec_param {cls.knn_conditions} AS vector_score]"
            )
            .sort_by("vector_score", asc=True)
            .paging(0, top)
            .return_fields("vector_score")
            # performance is optimized for sorting operations on DIALECT 4 in different scenarios.
            # check SORTBY details in https://redis.io/commands/ft.search/
            .dialect(4)
            .timeout(REDIS_QUERY_TIMEOUT)
        )
        params_dict = {
            "vec_param": np.array(query.vector).astype(np.float32).tobytes(),
            "K": top,
            "EF": cls.search_params["search_params"]["ef"],
            **params,
        }
        results = cls._ft.search(q, query_params=params_dict)

        return [(int(result.id), float(result.vector_score)) for result in results.docs]
