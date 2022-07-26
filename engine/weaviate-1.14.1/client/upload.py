import uuid

from weaviate import Client

from engine.base_client.upload import BaseUploader


class WeaviateUploader(BaseUploader):
    client = None
    collection = None

    @classmethod
    def init_client(cls, url, collection_name):
        cls.client = Client(url)
        cls.collection = collection_name

    @classmethod
    def upload_batch(cls, batch: list, ids: list):
        for id_, vector in zip(ids, batch):
            cls.client.batch.add_data_object(
                data_object={},
                class_name=cls.collection,
                uuid=uuid.UUID(int=id_).hex,
                vector=vector,
            )
        cls.client.batch.create_objects()
