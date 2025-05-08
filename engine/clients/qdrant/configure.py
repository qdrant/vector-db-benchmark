from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.qdrant.config import QDRANT_API_KEY, QDRANT_COLLECTION_NAME


class QdrantConfigurator(BaseConfigurator):
    SPARSE_VECTOR_SUPPORT = True
    DISTANCE_MAPPING = {
        Distance.L2: rest.Distance.EUCLID,
        Distance.COSINE: rest.Distance.COSINE,
        Distance.DOT: rest.Distance.DOT,
    }
    INDEX_TYPE_MAPPING = {
        "int": rest.PayloadSchemaType.INTEGER,
        "keyword": rest.PayloadSchemaType.KEYWORD,
        "text": rest.PayloadSchemaType.TEXT,
        "float": rest.PayloadSchemaType.FLOAT,
        "geo": rest.PayloadSchemaType.GEO,
    }
    INDEX_PARAMS_TYPE_MAPPING = {
        "int": rest.IntegerIndexParams,
        "keyword": rest.KeywordIndexParams,
        "text": rest.TextIndexParams,
        "float": rest.FloatIndexParams,
        "geo": rest.GeoIndexParams,
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)

        self.client = QdrantClient(
            url=host, api_key=QDRANT_API_KEY, **connection_params
        )

    def clean(self):
        self.client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)

    def recreate(self, dataset: Dataset, collection_params):
        if dataset.config.type == "sparse":
            vectors_config = {
                "vectors_config": {},
                "sparse_vectors_config": {
                    "sparse": rest.SparseVectorParams(
                        index=rest.SparseIndexParams(
                            on_disk=False,
                        )
                    )
                },
            }
        else:
            is_vectors_on_disk = self.collection_params.get("vectors_config", {}).get(
                "on_disk", False
            )
            self.collection_params.pop("vectors_config", None)

            vectors_config = {
                "vectors_config": (
                    rest.VectorParams(
                        size=dataset.config.vector_size,
                        distance=self.DISTANCE_MAPPING.get(dataset.config.distance),
                        on_disk=is_vectors_on_disk,
                    )
                )
            }

        payload_index_params = self.collection_params.pop("payload_index_params", {})
        if not set(payload_index_params.keys()).issubset(dataset.config.schema.keys()):
            raise ValueError("payload_index_params are not found in dataset schema")

        optimizers_config = self.collection_params.setdefault("optimizers_config", {})
        # By default, disable index building while uploading
        optimizers_config.setdefault("max_optimization_threads", 0)

        self.client.recreate_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            **vectors_config,
            **self.collection_params
        )

        for field_name, field_type in dataset.config.schema.items():
            if field_type in ["keyword", "uuid"]:
                is_tenant = payload_index_params.get(field_name, {}).get(
                    "is_tenant", None
                )
                on_disk = payload_index_params.get(field_name, {}).get("on_disk", None)

                self.client.create_payload_index(
                    collection_name=QDRANT_COLLECTION_NAME,
                    field_name=field_name,
                    field_schema=self.INDEX_PARAMS_TYPE_MAPPING.get(field_type)(
                        type=self.INDEX_TYPE_MAPPING.get(field_type),
                        is_tenant=is_tenant,
                        on_disk=on_disk,
                    ),
                )
            else:
                self.client.create_payload_index(
                    collection_name=QDRANT_COLLECTION_NAME,
                    field_name=field_name,
                    field_schema=self.INDEX_TYPE_MAPPING.get(field_type),
                )
