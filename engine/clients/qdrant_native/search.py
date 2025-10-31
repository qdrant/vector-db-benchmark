from typing import List, Tuple

import httpx

from dataset_reader.base_reader import Query
from engine.base_client.search import BaseSearcher
from engine.clients.qdrant_native.config import QDRANT_API_KEY, QDRANT_COLLECTION_NAME
from engine.clients.qdrant_native.parser import QdrantNativeConditionParser


class QdrantNativeSearcher(BaseSearcher):
    search_params = {}
    client: httpx.Client = None
    parser = QdrantNativeConditionParser()
    host = None
    headers = {}

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.host = f"http://{host.rstrip('/')}:6333"
        cls.search_params = search_params

        # Build headers
        cls.headers = {"Content-Type": "application/json"}
        if QDRANT_API_KEY:
            cls.headers["api-key"] = QDRANT_API_KEY

        # Create HTTP client
        timeout = connection_params.get("timeout", 30)
        cls.client = httpx.Client(
            headers=cls.headers,
            timeout=httpx.Timeout(timeout=timeout),
            limits=httpx.Limits(max_connections=None, max_keepalive_connections=0),
        )

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        """Execute a single search query using REST API"""
        url = f"{cls.host}/collections/{QDRANT_COLLECTION_NAME}/points/query"

        # Build the query vector
        if query.sparse_vector is None:
            # Dense vector query
            query_vector = query.vector
        else:
            # Sparse vector query
            query_vector = {
                "indices": query.sparse_vector.indices,
                "values": query.sparse_vector.values,
            }

        # Build the request payload
        payload = {
            "query": query_vector,
            "limit": top,
        }

        # Add 'using' parameter for sparse vectors
        if query.sparse_vector is not None:
            payload["using"] = "sparse"

        # Add filter if present
        query_filter = cls.parser.parse(query.meta_conditions)
        if query_filter:
            payload["filter"] = query_filter

        # Add search params configuration
        search_config = cls.search_params.get("config", {})
        if search_config:
            payload["params"] = search_config

        # Handle prefetch (for hybrid search)
        prefetch_config = cls.search_params.get("prefetch")
        if prefetch_config:
            prefetch = {
                **prefetch_config,
                "query": query_vector,
            }
            payload["prefetch"] = [prefetch]

        # Add with_payload option
        with_payload = cls.search_params.get("with_payload", False)
        payload["with_payload"] = with_payload

        try:
            response = cls.client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            # Extract results from response
            points = result["result"]["points"]
            return [(point["id"], point["score"]) for point in points]

        except Exception as ex:
            print(f"Something went wrong during search: {ex}")
            raise ex

    @classmethod
    def delete_client(cls):
        """Cleanup HTTP client"""
        if cls.client is not None:
            cls.client.close()
            cls.client = None