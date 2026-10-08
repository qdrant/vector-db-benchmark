import multiprocessing as mp
import uuid
from typing import List, Tuple

import backoff
from opensearchpy import OpenSearch
from opensearchpy.exceptions import TransportError

from dataset_reader.base_reader import Query
from engine.base_client.search import BaseSearcher
from engine.clients.opensearch.config import (
    OPENSEARCH_INDEX,
    OPENSEARCH_TIMEOUT,
    get_opensearch_client,
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
        cls.client = get_opensearch_client(host, connection_params)
        cls.search_params = search_params

    def _search_backoff_handler(details):
        print(
            f"Backing off OpenSearch query for {details['wait']} seconds after {details['tries']} tries due to {details['exception']}"
        )

    @classmethod
    @backoff.on_exception(
        backoff.expo,
        TransportError,
        max_time=OPENSEARCH_TIMEOUT,
        on_backoff=_search_backoff_handler,
    )
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        opensearch_query = {
            "knn": {
                "vector": {
                    "vector": query.vector,
                    "k": top,
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
                "timeout": OPENSEARCH_TIMEOUT,
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
                body=cls.search_params["config"], index=OPENSEARCH_INDEX
            )
