from opensearchpy import NotFoundError, OpenSearch

from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.opensearch.config import (
    OPENSEARCH_INDEX,
    OPENSEARCH_PASSWORD,
    OPENSEARCH_PORT,
    OPENSEARCH_USER,
)


class OpenSearchConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "l2",
        Distance.COSINE: "cosinesimil",
        Distance.DOT: "innerproduct",
    }
    INDEX_TYPE_MAPPING = {
        "int": "long",
        "geo": "geo_point",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        init_params = {
            **{
                "verify_certs": False,
                "request_timeout": 90,
                "retry_on_timeout": True,
            },
            **connection_params,
        }
        self.client = OpenSearch(
            f"http://{host}:{OPENSEARCH_PORT}",
            basic_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
            **init_params,
        )

    def clean(self):
        try:
            self.client.indices.delete(
                index=OPENSEARCH_INDEX,
                params={
                    "timeout": 300,
                },
            )
        except NotFoundError:
            pass

    def recreate(self, dataset: Dataset, collection_params):
        if dataset.config.distance == Distance.DOT:
            raise IncompatibilityError
        if dataset.config.vector_size > 1024:
            raise IncompatibilityError

        self.client.indices.create(
            index=OPENSEARCH_INDEX,
            body={
                "settings": {
                    "index": {
                        "knn": True,
                    }
                },
                "mappings": {
                    "properties": {
                        "vector": {
                            "type": "knn_vector",
                            "dimension": dataset.config.vector_size,
                            "method": {
                                **{
                                    "name": "hnsw",
                                    "engine": "lucene",
                                    "space_type": self.DISTANCE_MAPPING[
                                        dataset.config.distance
                                    ],
                                    "parameters": {
                                        "m": 16,
                                        "ef_construction": 100,
                                    },
                                },
                                **collection_params.get("method"),
                            },
                        },
                        **self._prepare_fields_config(dataset),
                    }
                },
            },
            params={
                "timeout": 300,
            },
            cluster_manager_timeout="5m",
        )

    def _prepare_fields_config(self, dataset: Dataset):
        return {
            field_name: {
                # The mapping is used only for several types, as some of them
                # overlap with the ones used internally.
                "type": self.INDEX_TYPE_MAPPING.get(field_type, field_type),
                "index": True,
            }
            for field_name, field_type in dataset.config.schema.items()
        }
