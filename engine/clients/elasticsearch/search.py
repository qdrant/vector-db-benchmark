import multiprocessing as mp
import uuid
from typing import List, Tuple

from elasticsearch import Elasticsearch

from engine.base_client.distances import Distance
from engine.base_client.search import BaseSearcher
from engine.clients.elasticsearch.config import (
    ELASTIC_INDEX,
    ELASTIC_PASSWORD,
    ELASTIC_PORT,
    ELASTIC_USER,
)
from engine.clients.elasticsearch.parser import ElasticConditionParser


class ClosableElastic(Elasticsearch):
    def __del__(self):
        self.close()


class ElasticSearcher(BaseSearcher):
    search_params = {}
    client: Elasticsearch = None
    parser = ElasticConditionParser()

    DISTANCE_SCRIPTS = {
        Distance.L2: "1 / (1 + l1norm(params.queryVector, 'vector'))",
        Distance.COSINE: "cosineSimilarity(params.query_vector, 'vector') + 1.0",
        Distance.DOT: "double value = dotProduct(params.query_vector, 'vector'); return sigmoid(1, Math.E, -value);",
    }

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
        cls.client: Elasticsearch = Elasticsearch(
            f"http://{host}:{ELASTIC_PORT}",
            basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
            **init_params,
        )
        cls.search_params = search_params
        cls.distance = distance

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        if "exact" in cls.search_params and cls.search_params["exact"]:
            res = cls.client.search(index=ELASTIC_INDEX, query={
                "script_score": {
                    "query": { "match_all": {} } if meta_conditions is None else meta_conditions,
                    "script": {
                        "source": cls.DISTANCE_SCRIPTS[cls.distance],
                        "params": {
                            "query_vector": vector
                        }
                    }
                }
            })

        else:
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
