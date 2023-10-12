import multiprocessing as mp
from typing import List, Tuple

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from engine.base_client.search import BaseSearcher
from engine.clients.qdrant.config import QDRANT_COLLECTION_NAME
from engine.clients.qdrant.parser import QdrantConditionParser


class QdrantSearcher(BaseSearcher):
    search_params = {}
    client: QdrantClient = None
    parser = QdrantConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.client: QdrantClient = QdrantClient(
            host,
            prefer_grpc=True,
            limits=httpx.Limits(max_connections=None, max_keepalive_connections=0),
            **connection_params
        )
        cls.search_params = search_params

    # Uncomment for gRPC
    # @classmethod
    # def get_mp_start_method(cls):
    #     return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        # return cls.client.count(collection_name=QDRANT_COLLECTION_NAME)
        res = cls.client.search(
            collection_name=QDRANT_COLLECTION_NAME,
            query_vector=vector,
            query_filter=cls.parser.parse(meta_conditions),
            limit=top,
            search_params=rest.SearchParams(
                **cls.search_params.get("search_params", {})
            ),
        )
        return [(hit.id, hit.score) for hit in res]

    @classmethod
    def delete_client(cls):
        if cls.client is not None:
            del cls.client
