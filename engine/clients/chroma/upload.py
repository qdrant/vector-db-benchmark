from typing import List

from chromadb import ClientAPI, HttpClient, Settings

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.chroma.config import CHROMA_COLLECTION_NAME, chroma_fix_host


class ChromaUploader(BaseUploader):
    client: ClientAPI = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.client = HttpClient(
            host=chroma_fix_host(host),
            settings=Settings(allow_reset=True, anonymized_telemetry=False),
            **connection_params,
        )
        cls.collection = cls.client.get_collection(name=CHROMA_COLLECTION_NAME)

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        ids, vectors, payloads = [], [], []
        for point in batch:
            ids.append(str(point.id))
            vectors.append(point.vector)
            payloads.append(point.metadata or None)

        cls.collection.add(
            embeddings=vectors,
            metadatas=payloads or None,
            ids=ids,
        )
