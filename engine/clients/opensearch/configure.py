from opensearchpy import NotFoundError

from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.opensearch.config import (
    OPENSEARCH_INDEX,
    OPENSEARCH_INDEX_TIMEOUT,
    get_opensearch_client,
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
        self.client = get_opensearch_client(host, connection_params)

    def clean(self):
        try:
            self.client.indices.delete(
                index=OPENSEARCH_INDEX,
                params={
                    "timeout": OPENSEARCH_INDEX_TIMEOUT,
                },
            )
        except NotFoundError:
            pass

    def recreate(self, dataset: Dataset, collection_params):
        if dataset.config.distance == Distance.DOT:
            raise IncompatibilityError
        # The knn_vector data type supports a vector of floats that can have a dimension count of up to 16,000 for the NMSLIB, Faiss, and Lucene engines, as set by the dimension mapping parameter.
        # Source
        if dataset.config.vector_size > 16000:
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
