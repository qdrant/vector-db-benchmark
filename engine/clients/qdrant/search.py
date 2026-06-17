import os
from typing import List, Optional, Tuple

import httpx
from qdrant_client import QdrantClient, models
from qdrant_client._pydantic_compat import construct

from dataset_reader.base_reader import Query
from engine.base_client.search import BaseSearcher
from engine.clients.qdrant.config import QDRANT_API_KEY, QDRANT_COLLECTION_NAME
from engine.clients.qdrant.parser import QdrantConditionParser


class QdrantSearcher(BaseSearcher):
    search_params = {}
    client: QdrantClient = None
    parser = QdrantConditionParser()
    _last_server_latency: Optional[float] = None

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.client: QdrantClient = QdrantClient(
            url=host,
            prefer_grpc=False,  # REST gives us server-side time in the response
            api_key=QDRANT_API_KEY,
            limits=httpx.Limits(max_connections=None, max_keepalive_connections=20),
            **connection_params,
        )
        cls.search_params = search_params
        cls._last_server_latency = None

    @classmethod
    def server_latency(cls) -> Optional[float]:
        return cls._last_server_latency

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        if query.sparse_vector is None:
            query_vector = query.vector
        else:
            query_vector = construct(
                models.SparseVector,
                indices=query.sparse_vector.indices,
                values=query.sparse_vector.values,
            )

        prefetch = cls.search_params.get("prefetch")
        if prefetch:
            prefetch = models.Prefetch(**prefetch, query=query_vector)

        try:
            query_request = models.QueryRequest(
                prefetch=prefetch,
                query=query_vector,
                using="sparse" if query.sparse_vector else None,
                filter=cls.parser.parse(query.meta_conditions),
                params=models.SearchParams(**cls.search_params.get("config", {})),
                limit=top,
                with_vector=False,
                with_payload=cls.search_params.get("with_payload", False),
            )
            raw = cls.client.http.search_api.query_points(
                collection_name=QDRANT_COLLECTION_NAME,
                query_request=query_request,
            )
            cls._last_server_latency = raw.time
            result = raw.result
            assert result is not None
        except Exception as ex:
            print(f"Something went wrong during search: {ex}")
            raise RuntimeError(f"{type(ex).__name__}: {ex}") from None

        return [(hit.id, hit.score) for hit in result.points]
