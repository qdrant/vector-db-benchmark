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
    # Pre-computed request components for benchmark accuracy
    search_url = None
    payload_template = None
    prefetch_config = None

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.host = f"http://{host.rstrip('/')}:6333"
        cls.search_params = search_params

        # Pre-build URL once
        cls.search_url = f"{cls.host}/collections/{QDRANT_COLLECTION_NAME}/points/query"

        # Pre-build payload template with static fields
        cls.payload_template = {
            "with_payload": search_params.get("with_payload", False),
        }
        search_config = search_params.get("config", {})
        if search_config:
            cls.payload_template["params"] = search_config

        # Cache prefetch config
        cls.prefetch_config = search_params.get("prefetch")

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
        # Start from pre-built template (shallow copy is sufficient)
        payload = cls.payload_template.copy()
        payload["limit"] = top

        if query.sparse_vector is None:
            payload["query"] = query.vector
        else:
            # Convert numpy types to native Python types for JSON serialization
            query_vector = {
                "indices": [int(i) for i in query.sparse_vector.indices],
                "values": [float(v) for v in query.sparse_vector.values],
            }
            payload["query"] = query_vector
            payload["using"] = "sparse"

        query_filter = cls.parser.parse(query.meta_conditions)
        if query_filter:
            payload["filter"] = query_filter

        if cls.prefetch_config:
            payload["prefetch"] = [{
                **cls.prefetch_config,
                "query": payload["query"],
            }]

        try:
            response = cls.client.post(cls.search_url, json=payload)
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
