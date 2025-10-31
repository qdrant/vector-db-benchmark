import time
from typing import List

import httpx

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.qdrant_native.config import QDRANT_API_KEY, QDRANT_COLLECTION_NAME


class QdrantNativeUploader(BaseUploader):
    client = None
    upload_params = {}
    host = None
    headers = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.host = f"http://{host.rstrip('/')}:6333"
        cls.upload_params = upload_params

        # Build headers
        cls.headers = {"Content-Type": "application/json"}
        if QDRANT_API_KEY:
            cls.headers["api-key"] = QDRANT_API_KEY

        # Create HTTP client with connection pooling
        timeout = connection_params.get("timeout", 30)
        cls.client = httpx.Client(
            headers=cls.headers,
            timeout=httpx.Timeout(timeout=timeout),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        """Upload a batch of records using REST API"""
        # Build the batch payload
        points = []
        for point in batch:
            point_data = {
                "id": point.id,
                "payload": point.metadata or {},
            }

            # Handle vector (dense or sparse)
            if point.sparse_vector is None:
                # Dense vector
                point_data["vector"] = point.vector
            else:
                # Sparse vector
                point_data["vector"] = {
                    "sparse": {
                        "indices": point.sparse_vector.indices,
                        "values": point.sparse_vector.values,
                    }
                }

            points.append(point_data)

        # Upsert the batch
        url = f"{cls.host}/collections/{QDRANT_COLLECTION_NAME}/points"
        payload = {
            "points": points,
        }

        response = cls.client.put(url, json=payload, params={"wait": "false"})
        response.raise_for_status()

    @classmethod
    def post_upload(cls, _distance):
        """
        Post-upload operations:
        1. Enable index optimization if it was disabled
        2. Wait for collection to become GREEN
        """
        # Get current collection info
        url = f"{cls.host}/collections/{QDRANT_COLLECTION_NAME}"
        response = cls.client.get(url)
        response.raise_for_status()
        collection_info = response.json()["result"]

        # Check if optimization was disabled
        max_optimization_threads = collection_info["config"]["optimizer_config"].get(
            "max_optimization_threads", 1
        )

        if max_optimization_threads == 0:
            # Enable optimization
            patch_url = f"{cls.host}/collections/{QDRANT_COLLECTION_NAME}"
            patch_payload = {
                "optimizers_config": {
                    "max_optimization_threads": 100_000,
                }
            }
            response = cls.client.patch(patch_url, json=patch_payload)
            response.raise_for_status()

        # Wait for collection to become GREEN
        cls.wait_collection_green()
        return {}

    @classmethod
    def wait_collection_green(cls):
        """Wait for collection status to be GREEN"""
        wait_time = 5.0
        total = 0
        url = f"{cls.host}/collections/{QDRANT_COLLECTION_NAME}"

        while True:
            time.sleep(wait_time)
            total += wait_time

            response = cls.client.get(url)
            response.raise_for_status()
            collection_info = response.json()["result"]

            if collection_info["status"] != "green":
                continue

            # Check twice to ensure stability
            time.sleep(wait_time)
            response = cls.client.get(url)
            response.raise_for_status()
            collection_info = response.json()["result"]

            if collection_info["status"] == "green":
                break

        return total

    @classmethod
    def delete_client(cls):
        """Cleanup HTTP client"""
        if cls.client is not None:
            cls.client.close()
            cls.client = None