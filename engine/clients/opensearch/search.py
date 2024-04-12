import multiprocessing as mp
import uuid
from typing import List, Tuple

from opensearchpy import OpenSearch

from engine.base_client.search import BaseSearcher
from engine.clients.opensearch.config import (
    OPENSEARCH_INDEX,
    OPENSEARCH_PASSWORD,
    OPENSEARCH_PORT,
    OPENSEARCH_USER,
)
from engine.clients.opensearch.parser import OpenSearchConditionParser


class ClosableOpenSearch(OpenSearch):
    def __del__(self):
        self.close()


class OpenSearchSearcher(BaseSearcher):
    search_params = {}
    client: OpenSearch = None
    parser = OpenSearchConditionParser()

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
        cls.client: OpenSearch = OpenSearch(
            f"http://{host}:{OPENSEARCH_PORT}",
            basic_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
            **init_params,
        )
        cls.search_params = search_params

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        query = {
            "knn": {
                "vector": {
                    "vector": vector,
                    "k": top,
                }
            }
        }

        meta_conditions = cls.parser.parse(meta_conditions)
        if meta_conditions:
            query = {
                "bool": {
                    "must": [query],
                    "filter": meta_conditions,
                }
            }

        res = cls.client.search(
            index=OPENSEARCH_INDEX,
            body={
                "query": query,
                "size": top,
            },
            params={
                "timeout": 60,
            },
        )
        return [
            (uuid.UUID(hex=hit["_id"]).int, hit["_score"])
            for hit in res["hits"]["hits"]
        ]

    @classmethod
    def setup_search(cls):
        if cls.search_params:
            cls.client.indices.put_settings(
                body=cls.search_params["params"], index=OPENSEARCH_INDEX
            )
