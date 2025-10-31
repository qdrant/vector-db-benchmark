import httpx

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.qdrant_native.config import QDRANT_API_KEY, QDRANT_COLLECTION_NAME


class QdrantNativeConfigurator(BaseConfigurator):
    SPARSE_VECTOR_SUPPORT = True
    DISTANCE_MAPPING = {
        Distance.L2: "Euclid",
        Distance.COSINE: "Cosine",
        Distance.DOT: "Dot",
    }
    INDEX_TYPE_MAPPING = {
        "int": "integer",
        "keyword": "keyword",
        "text": "text",
        "float": "float",
        "geo": "geo",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)

        self.host = f"http://{host.rstrip('/')}:6333"
        self.connection_params = connection_params

        self.headers = {"Content-Type": "application/json"}
        if QDRANT_API_KEY:
            self.headers["api-key"] = QDRANT_API_KEY

        timeout = connection_params.get("timeout", 30)
        self.client = httpx.Client(
            headers=self.headers,
            timeout=httpx.Timeout(timeout=timeout),
        )

    def clean(self):
        """Delete the collection"""
        url = f"{self.host}/collections/{QDRANT_COLLECTION_NAME}"
        response = self.client.delete(url)
        # 404 is ok if collection doesn't exist
        if response.status_code not in [200, 404]:
            response.raise_for_status()

    def recreate(self, dataset: Dataset, collection_params):
        """Create collection with proper configuration"""
        url = f"{self.host}/collections/{QDRANT_COLLECTION_NAME}"

        # Build vectors configuration
        if dataset.config.type == "sparse":
            vectors_config = {}
            sparse_vectors_config = {
                "sparse": {
                    "index": {
                        "on_disk": False,
                    }
                }
            }
        else:
            is_vectors_on_disk = self.collection_params.get("vectors_config", {}).get(
                "on_disk", False
            )
            self.collection_params.pop("vectors_config", None)

            vectors_config = {
                "size": dataset.config.vector_size,
                "distance": self.DISTANCE_MAPPING.get(dataset.config.distance),
                "on_disk": is_vectors_on_disk,
            }
            sparse_vectors_config = None

        payload_index_params = self.collection_params.pop("payload_index_params", {})
        if not set(payload_index_params.keys()).issubset(dataset.config.schema.keys()):
            raise ValueError("payload_index_params are not found in dataset schema")

        # Set optimizers config - disable index building during upload by default
        optimizers_config = self.collection_params.setdefault("optimizers_config", {})
        optimizers_config.setdefault("max_optimization_threads", 0)

        # Build the collection creation payload
        payload = {}
        if vectors_config:
            payload["vectors"] = vectors_config
        if sparse_vectors_config:
            payload["sparse_vectors"] = sparse_vectors_config

        for key, value in self.collection_params.items():
            payload[key] = value

        response = self.client.put(url, json=payload)
        response.raise_for_status()

        for field_name, field_type in dataset.config.schema.items():
            self._create_payload_index(field_name, field_type, payload_index_params)

    def _create_payload_index(
        self, field_name: str, field_type: str, payload_index_params: dict
    ):
        """Create a payload index for a specific field"""
        url = f"{self.host}/collections/{QDRANT_COLLECTION_NAME}/index"

        # Build the field schema based on type
        if field_type in ["keyword", "uuid"]:
            field_schema = {
                "type": self.INDEX_TYPE_MAPPING.get(field_type, "keyword"),
            }

            # Add optional parameters if provided
            params = payload_index_params.get(field_name, {})
            if "is_tenant" in params and params["is_tenant"] is not None:
                field_schema["is_tenant"] = params["is_tenant"]
            if "on_disk" in params and params["on_disk"] is not None:
                field_schema["on_disk"] = params["on_disk"]
        else:
            # For other types, just use the type string
            field_schema = self.INDEX_TYPE_MAPPING.get(field_type, field_type)

        payload = {
            "field_name": field_name,
            "field_schema": field_schema,
        }

        response = self.client.put(url, json=payload)
        response.raise_for_status()

    def delete_client(self):
        """Cleanup HTTP client"""
        if hasattr(self, "client") and self.client is not None:
            self.client.close()
