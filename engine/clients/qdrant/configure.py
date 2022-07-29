from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.qdrant.config import QDRANT_COLLECTION_NAME


class QdrantConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: rest.Distance.EUCLID,
        Distance.COSINE: rest.Distance.COSINE,
        Distance.DOT: rest.Distance.DOT,
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)

        self.client = QdrantClient(host=host, **connection_params)

    def clean(self):
        self.client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)

    def recreate(
        self,
        distance,
        vector_size,
        collection_params,
    ):
        self.client.recreate_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vector_size=vector_size,
            distance=self.DISTANCE_MAPPING.get(distance),
            **self.collection_params
        )
