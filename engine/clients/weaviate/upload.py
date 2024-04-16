import uuid
from typing import List

from weaviate import WeaviateClient
from weaviate.classes.data import DataObject
from weaviate.connect import ConnectionParams

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.weaviate.config import WEAVIATE_CLASS_NAME, WEAVIATE_DEFAULT_PORT


class WeaviateUploader(BaseUploader):
    client: WeaviateClient = None
    upload_params = {}
    collection = None

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        url = f"http://{host}:{connection_params.get('port', WEAVIATE_DEFAULT_PORT)}"
        cls.client = WeaviateClient(
            ConnectionParams.from_url(url, 50051), skip_init_checks=True
        )
        cls.client.connect()
        cls.upload_params = upload_params
        cls.connection_params = connection_params
        cls.collection = cls.client.collections.get(
            WEAVIATE_CLASS_NAME, skip_argument_validation=True
        )

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        objects = []
        for record in batch:
            _id = uuid.UUID(int=record.id)
            _property = record.metadata or {}
            objects.append(
                DataObject(properties=_property, vector=record.vector, uuid=_id)
            )
        if len(objects) > 0:
            cls.collection.data.insert_many(objects)

    @classmethod
    def delete_client(cls):
        if cls.client is not None:
            cls.client.close()
