from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, MilvusException
from pymilvus.orm import utility

from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.milvus.config import (
    MILVUS_COLLECTION_NAME,
    MILVUS_DEFAULT_ALIAS,
    MILVUS_DEFAULT_PORT,
)


class MilvusConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "L2",
        Distance.DOT: "IP",
        # Milvus does not support cosine. Cosine is equal to IP of normalized vectors
        Distance.COSINE: "Cosine"
        # Jaccard, Tanimoto, Hamming distance, Superstructure and Substructure are also available
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self.client = connections.connect(
            alias=MILVUS_DEFAULT_ALIAS,
            host=host,
            port=str(connection_params.pop("port", MILVUS_DEFAULT_PORT)),
            **connection_params
        )
        print("established connection")

    def clean(self):
        try:
            utility.drop_collection(MILVUS_COLLECTION_NAME, using=MILVUS_DEFAULT_ALIAS)
            utility.has_collection(MILVUS_COLLECTION_NAME, using=MILVUS_DEFAULT_ALIAS)
        except MilvusException:
            pass

    def recreate(
        self,
        distance,
        vector_size,
        collection_params,
    ):
        idx = FieldSchema(
            name="id",
            dtype=DataType.INT64,
            is_primary=True,
        )
        vector = FieldSchema(
            name="vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=vector_size,
        )
        schema = CollectionSchema(
            fields=[idx, vector], description=MILVUS_COLLECTION_NAME
        )

        collection = Collection(
            name=MILVUS_COLLECTION_NAME,
            schema=schema,
            using=MILVUS_DEFAULT_ALIAS,
        )

        for index in collection.indexes:
            index.drop()

        resolved_distance = self.DISTANCE_MAPPING.get(distance)
        metric_type = (
            resolved_distance
            if resolved_distance != "Cosine"
            else self.DISTANCE_MAPPING.get(Distance.DOT)
        )
        index_params = {
            "metric_type": metric_type,
            "index_type": collection_params.pop("index_type", "HNSW"),
            **collection_params,
        }

        collection.create_index(field_name="vector", index_params=index_params)

        return {"normalize": resolved_distance == "Cosine"}
