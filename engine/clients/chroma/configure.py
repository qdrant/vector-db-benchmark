from chromadb import HttpClient, Settings

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.chroma.config import CHROMA_COLLECTION_NAME, chroma_fix_host


class ChromaConfigurator(BaseConfigurator):

    DISTANCE_MAPPING = {
        Distance.L2: "l2",
        Distance.COSINE: "cosine",
        Distance.DOT: "ip",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self.client = HttpClient(
            host=chroma_fix_host(host),
            settings=Settings(allow_reset=True, anonymized_telemetry=False),
            **connection_params,
        )

    def clean(self):
        """
        Delete a collection and all associated embeddings, documents, and metadata.

        This is destructive and not reversible.
        """
        try:
            self.client.delete_collection(name=CHROMA_COLLECTION_NAME)
        except (Exception, ValueError):
            pass

    def recreate(self, dataset: Dataset, collection_params):
        params = self.collection_params
        params["metadata"] = dict(
            {"hnsw:space": self.DISTANCE_MAPPING.get(dataset.config.distance)},
            **params.pop("config", {}),
        )
        self.client.create_collection(
            name=CHROMA_COLLECTION_NAME,
            **params,
        )
