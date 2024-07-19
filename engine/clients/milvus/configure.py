from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
)
from pymilvus.exceptions import DataTypeNotSupportException
from pymilvus.orm import utility

from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.milvus.config import (
    DTYPE_EXTRAS,
    MILVUS_COLLECTION_NAME,
    MILVUS_DEFAULT_ALIAS,
    get_milvus_client,
)


class MilvusConfigurator(BaseConfigurator):
    DTYPE_MAPPING = {
        "int": DataType.INT64,
        "keyword": DataType.VARCHAR,
        "text": DataType.VARCHAR,
        "float": DataType.DOUBLE,
        "geo": DataType.UNKNOWN,
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self.client = get_milvus_client(connection_params, host, MILVUS_DEFAULT_ALIAS)
        print("established connection")

    def clean(self):
        if utility.has_collection(MILVUS_COLLECTION_NAME, using=MILVUS_DEFAULT_ALIAS):
            print("dropping collection named {MILVUS_COLLECTION_NAME}...")
            utility.drop_collection(MILVUS_COLLECTION_NAME, using=MILVUS_DEFAULT_ALIAS)
            print("dropped collection named {MILVUS_COLLECTION_NAME}...")
        assert (
            utility.has_collection(MILVUS_COLLECTION_NAME, using=MILVUS_DEFAULT_ALIAS)
            is False
        )

    def recreate(self, dataset: Dataset, collection_params):
        idx = FieldSchema(
            name="id",
            dtype=DataType.INT64,
            is_primary=True,
        )
        vector = FieldSchema(
            name="vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=dataset.config.vector_size,
        )
        fields = [idx, vector]
        for field_name, field_type in dataset.config.schema.items():
            try:
                field_schema = FieldSchema(
                    name=field_name,
                    dtype=self.DTYPE_MAPPING.get(field_type),
                    **DTYPE_EXTRAS.get(field_type, {}),
                )
                fields.append(field_schema)
            except DataTypeNotSupportException as e:
                raise IncompatibilityError(e)
        schema = CollectionSchema(fields=fields, description=MILVUS_COLLECTION_NAME)

        collection = Collection(
            name=MILVUS_COLLECTION_NAME,
            schema=schema,
            using=MILVUS_DEFAULT_ALIAS,
        )

        for index in collection.indexes:
            index.drop()

    def execution_params(self, distance, vector_size):
        return {"normalize": distance == Distance.COSINE}
