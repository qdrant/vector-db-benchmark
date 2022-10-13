import multiprocessing as mp
from typing import List, Optional

from pymilvus import Collection, connections

from engine.base_client.upload import BaseUploader
from engine.clients.milvus.config import (
    MILVUS_COLLECTION_NAME,
    MILVUS_DEFAULT_ALIAS,
    MILVUS_DEFAULT_PORT, DISTANCE_MAPPING,
)


class MilvusUploader(BaseUploader):
    client = None
    upload_params = {}
    collection: Collection = None
    distance: str = None

    @classmethod
    def get_mp_start_method(cls):
        return 'forkserver' if 'forkserver' in mp.get_all_start_methods() else 'spawn'

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.client = connections.connect(
            alias=MILVUS_DEFAULT_ALIAS,
            host=host,
            port=str(connection_params.pop("port", MILVUS_DEFAULT_PORT)),
            **connection_params
        )
        cls.collection = Collection(MILVUS_COLLECTION_NAME, using=MILVUS_DEFAULT_ALIAS)
        cls.upload_params = upload_params
        cls.distance = DISTANCE_MAPPING[distance]

    @classmethod
    def upload_batch(
        cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]
    ):
        # TODO: use metadata and upload to the index
        cls.collection.insert([ids, vectors])

    @classmethod
    def post_upload(cls, distance):
        index_params = {
            "metric_type": cls.distance,
            "index_type": "HNSW",
            "params": {
                **cls.upload_params.get('index_params', {})
            }
        }

        cls.collection.create_index(field_name="vector", index_params=index_params)

        cls.collection.load()
        return {}
