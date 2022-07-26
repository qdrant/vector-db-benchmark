from typing import Optional, List

from qdrant_client import QdrantClient
from qdrant_client.http.models import Batch

from engine.base_client.upload import BaseUploader
from engine.clients.qdrant.config import QDRANT_COLLECTION_NAME


class QdrantUploader(BaseUploader):
    client = None

    @classmethod
    def init_client(cls, host, connection_params):
        cls.client = QdrantClient(
            host=host, prefer_grpc=connection_params.get("prefer_grpc", True)
        )

    @classmethod
    def upload_batch(
            cls,
            ids: List[int],
            vectors: List[list],
            metadata: Optional[List[dict]]
    ):
        cls.client.upsert(
            collection_name=QDRANT_COLLECTION_NAME,
            points=Batch(ids=ids, vectors=vectors, payloads=metadata),
        )
