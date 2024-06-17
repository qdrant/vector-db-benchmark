import multiprocessing as mp
from typing import List

from pymilvus import (
    Collection,
    MilvusException,
    connections,
    wait_for_index_building_complete,
)

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.milvus.config import (
    DISTANCE_MAPPING,
    DTYPE_DEFAULT,
    MILVUS_COLLECTION_NAME,
    MILVUS_DEFAULT_ALIAS,
    MILVUS_DEFAULT_PORT,
)


class MilvusUploader(BaseUploader):
    client = None
    upload_params = {}
    collection: Collection = None
    distance: str = None

    @classmethod
    def get_mp_start_method(cls):
        return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.client = connections.connect(
            alias=MILVUS_DEFAULT_ALIAS,
            host=host,
            port=str(connection_params.get("port", MILVUS_DEFAULT_PORT)),
            **connection_params
        )
        cls.collection = Collection(MILVUS_COLLECTION_NAME, using=MILVUS_DEFAULT_ALIAS)
        cls.upload_params = upload_params
        cls.distance = DISTANCE_MAPPING[distance]

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        has_metadata = any(record.metadata for record in batch)
        if has_metadata:
            field_values = [
                [
                    record.metadata.get(field_schema.name)
                    or DTYPE_DEFAULT[field_schema.dtype]
                    for record in batch
                ]
                for field_schema in cls.collection.schema.fields
                if field_schema.name not in ["id", "vector"]
            ]
        else:
            field_values = []

        ids, vectors = [], []
        for record in batch:
            ids.append(record.id)
            vectors.append(record.vector)

        cls.collection.insert([ids, vectors] + field_values)

    @classmethod
    def post_upload(cls, distance):
        index_params = {
            "metric_type": cls.distance,
            "index_type": cls.upload_params.get("index_type", "HNSW"),
            "params": {**cls.upload_params.get("index_params", {})},
        }
        cls.collection.flush()
        cls.collection.create_index(field_name="vector", index_params=index_params)
        for field_schema in cls.collection.schema.fields:
            if field_schema.name in ["id", "vector"]:
                continue
            try:
                cls.collection.create_index(
                    field_name=field_schema.name, index_name=field_schema.name
                )
            except MilvusException as e:
                # Code 1 means there is already an index for that column
                if 1 != e.code:
                    raise e

        for index in cls.collection.indexes:
            wait_for_index_building_complete(
                MILVUS_COLLECTION_NAME,
                index_name=index.index_name,
                using=MILVUS_DEFAULT_ALIAS,
            )

        cls.collection.load()
        return {}
