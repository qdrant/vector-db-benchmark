from qdrant_client import QdrantClient
from qdrant_client.http import models as rest


from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance


class QdrantConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2_SQUARED: rest.Distance.EUCLID,
        Distance.COSINE: rest.Distance.COSINE,
        Distance.DOT: rest.Distance.DOT,
    }

    def __init__(self, host, port, prefer_grpc=False):
        super().__init__()
        self.client = QdrantClient(host=host, port=port, prefer_grpc=prefer_grpc)

    def clean(self, collection_name):
        self.client.delete_collection(collection_name=collection_name)

    def recreate(self, collection_name, ef_construction, max_connections, distance, vector_size):
        self.client.recreate_collection(
            collection_name=collection_name,
            vector_size=vector_size,
            distance=self.DISTANCE_MAPPING.get(distance),

        )
