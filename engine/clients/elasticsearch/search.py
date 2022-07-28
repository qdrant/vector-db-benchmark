import uuid
from typing import Tuple, List

from elasticsearch import Elasticsearch

from engine.base_client.search import BaseSearcher
from engine.clients.elasticsearch import ELASTIC_PORT, ELASTIC_USER, ELASTIC_PASSWORD, ELASTIC_INDEX


class ElasticSearcher(BaseSearcher):
    search_params = {}
    client: Elasticsearch = None

    @classmethod
    def init_client(cls, host, connection_params: dict, search_params: dict):
        cls.client: Elasticsearch = Elasticsearch(
            f"http://{host}:{ELASTIC_PORT}",
            basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
            **{
                **{
                    "verify_certs": False,
                    "request_timeout": 90,
                    "retry_on_timeout": True,
                },
                **connection_params
            }
        )
        cls.search_params = search_params

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        res = cls.client.knn_search(
            index=ELASTIC_INDEX,
            knn={
                "field": "vector",
                "query_vector": vector,
                "k": 10,
                **{
                    "num_candidates": 100,
                    **cls.search_params
                }
            },
        )
        return [(uuid.UUID(hex=hit["_id"]).int, hit["_score"]) for hit in res["hits"]["hits"]]
