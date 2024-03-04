import multiprocessing as mp
import uuid
from typing import List, Tuple

from elasticsearch import Elasticsearch

from engine.base_client.search import BaseSearcher
from engine.clients.elasticsearch.config import (
    ELASTIC_INDEX,
    get_es_client,
)
from engine.clients.elasticsearch.parser import ElasticConditionParser


class ClosableElastic(Elasticsearch):
    def __del__(self):
        self.close()


class ElasticSearcher(BaseSearcher):
    search_params = {}
    client: Elasticsearch = None
    parser = ElasticConditionParser()

    @classmethod
    def get_mp_start_method(cls):
        return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        init_params = {
            **{
                "verify_certs": False,
                "request_timeout": 90,
                "retry_on_timeout": True,
            },
            **connection_params,
        }
        cls.client = get_es_client(host, connection_params)
        cls.search_params = search_params

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        knn = {
            "field": "vector",
            "query_vector": vector,
            "k": top,
            **{"num_candidates": 100, **cls.search_params},
        }

        meta_conditions = cls.parser.parse(meta_conditions)
        if meta_conditions:
            knn["filter"] = meta_conditions

        res = cls.client.search(
            index=ELASTIC_INDEX,
            knn=knn,
            size=top,
        )
        return [
            (uuid.UUID(hex=hit["_id"]).int, hit["_score"])
            for hit in res["hits"]["hits"]
        ]
