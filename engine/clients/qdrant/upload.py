import time
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import Batch, CollectionStatus

from engine.base_client.upload import BaseUploader
from engine.clients.qdrant.config import QDRANT_COLLECTION_NAME


class QdrantUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, connection_params, upload_params):
        cls.client = QdrantClient(host=host, **connection_params)
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(
        cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]
    ):
        cls.client.upsert(
            collection_name=QDRANT_COLLECTION_NAME,
            points=Batch(
                ids=ids,
                vectors=vectors,
                payloads=[payload or {} for payload in metadata],
            ),
        )

    @classmethod
    def post_upload(cls):
        cls.wait_collection_green()
        return {}

    @classmethod
    def wait_collection_green(cls):
        wait_time = 1.0
        total = 0
        collection_info = cls.client.get_collection(QDRANT_COLLECTION_NAME)
        while collection_info.status != CollectionStatus.GREEN:
            time.sleep(wait_time)
            total += wait_time
            collection_info = cls.client.get_collection(QDRANT_COLLECTION_NAME)
        return total
