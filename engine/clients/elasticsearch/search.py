import multiprocessing as mp
import uuid
from typing import List, Tuple

from elasticsearch import Elasticsearch

from engine.base_client.search import BaseSearcher
from engine.clients.elasticsearch.config import (
    ELASTIC_INDEX,
)
from engine.clients.elasticsearch.config import get_es_client
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
    def init_client(cls, host, _distance, connection_params: dict, search_params: dict):
        cls.client = get_es_client(host, connection_params)
        cls.search_params = search_params

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        knn = {
            "field": "vector",
            "query_vector": vector,
            "k": top,
            **cls.search_params["params"],
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
