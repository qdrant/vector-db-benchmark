import multiprocessing as mp
import uuid
from typing import List, Tuple

from opensearchpy import OpenSearch

from dataset_reader.base_reader import Query
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
        cls.distance = distance
        cls.search_params = search_params

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        opensearch_query = {
            "knn": {
                "vector": {
                    "vector": query.vector,
                    "k": top,
                    "method_parameters": {
                        "ef_search": cls.search_params["config"][
                            "ef_search"
                        ]  # ef_search parameter is added in the query time
                    },
                }
            }
        }

        meta_conditions = cls.parser.parse(query.meta_conditions)
        if meta_conditions:
            opensearch_query["knn"]["vector"]["filter"] = meta_conditions

        res = cls.client.search(
            index=OPENSEARCH_INDEX,
            body={
                "query": opensearch_query,
                "size": top,
            },
            params={
                "timeout": 60,
            },
            _source=False,
            docvalue_fields=["_id"],
            stored_fields="_none_",
        )

        return [
            (uuid.UUID(hex=hit["fields"]["_id"][0]).int, hit["_score"])
            for hit in res["hits"]["hits"]
        ]

    @classmethod
    def setup_search(cls):
        # Load the graphs in memory
        warmup_endpoint = f"/_plugins/_knn/warmup/{OPENSEARCH_INDEX}"
        cls.client.transport.perform_request("GET", warmup_endpoint)
