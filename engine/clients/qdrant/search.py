import os
from typing import List, Tuple

import httpx
from qdrant_client import QdrantClient
from qdrant_client._pydantic_compat import construct
from qdrant_client.http import models as rest

from dataset_reader.base_reader import Query
from engine.base_client.search import BaseSearcher
from engine.clients.qdrant.config import QDRANT_COLLECTION_NAME
from engine.clients.qdrant.parser import QdrantConditionParser


class QdrantSearcher(BaseSearcher):
    search_params = {}
    client: QdrantClient = None
    parser = QdrantConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "true"
        os.environ["GRPC_POLL_STRATEGY"] = "epoll,poll"
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
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        # Can query only one till we introduce re-ranking in the benchmarks
        if query.sparse_vector is None:
            query_vector = query.vector
        else:
            query_vector = construct(
                rest.NamedSparseVector,
                name="sparse",
                vector=construct(
                    rest.SparseVector,
                    indices=query.sparse_vector.indices,
                    values=query.sparse_vector.values,
                ),
            )

        res = cls.client.search(
            collection_name=QDRANT_COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=cls.parser.parse(query.meta_conditions),
            limit=top,
            search_params=rest.SearchParams(**cls.search_params.get("config", {})),
        )
        return [(hit.id, hit.score) for hit in res]
