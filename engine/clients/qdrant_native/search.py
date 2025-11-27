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
        # Use longer timeout for write operations to handle large query payloads
        base_timeout = connection_params.get("timeout", 30)
        cls.client = httpx.Client(
            headers=cls.headers,
            timeout=httpx.Timeout(
                connect=base_timeout,
                read=base_timeout,
                write=base_timeout * 5,  # 5x longer for writes
                pool=base_timeout,
            ),
            limits=httpx.Limits(max_connections=None, max_keepalive_connections=0),
        )

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        """Execute a single search query using REST API"""
        url = f"{cls.host}/collections/{QDRANT_COLLECTION_NAME}/points/query"

        if query.sparse_vector is None:
            query_vector = query.vector
        else:
            # Convert numpy types to native Python types for JSON serialization
            query_vector = {
                "indices": [int(i) for i in query.sparse_vector.indices],
                "values": [float(v) for v in query.sparse_vector.values],
            }

        payload = {
            "query": query_vector,
            "limit": top,
        }

        if query.sparse_vector is not None:
            payload["using"] = "sparse"

        query_filter = cls.parser.parse(query.meta_conditions)
        if query_filter:
            payload["filter"] = query_filter

        search_config = cls.search_params.get("config", {})
        if search_config:
            payload["params"] = search_config

        prefetch_config = cls.search_params.get("prefetch")
        if prefetch_config:
            prefetch = {
                **prefetch_config,
                "query": query_vector,
            }
            payload["prefetch"] = [prefetch]

        with_payload = cls.search_params.get("with_payload", False)
        payload["with_payload"] = with_payload

        try:
            response = cls.client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

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
