import uuid
from typing import Optional, List

from weaviate import Client

from engine.base_client.upload import BaseUploader
from engine.clients.weaviate.config import WEAVIATE_CLASS_NAME, WEAVIATE_DEFAULT_PORT


class WeaviateUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, connection_params, upload_params):
        url = f"http://{host}:{connection_params.pop('port', WEAVIATE_DEFAULT_PORT)}"
        cls.client = Client(url, **connection_params)

        cls.upload_params = upload_params
        cls.connection_params = connection_params

    @classmethod
    def upload_batch(
            cls,
            ids: List[int],
            vectors: List[list],
            metadata: List[Optional[dict]]
    ):
        for id_, vector, data_object in zip(ids, vectors, metadata):
            cls.client.batch.add_data_object(
                data_object=data_object,
                class_name=WEAVIATE_CLASS_NAME,
                uuid=uuid.UUID(int=id_).hex,
                vector=vector,
            )
        cls.client.batch.create_objects()
