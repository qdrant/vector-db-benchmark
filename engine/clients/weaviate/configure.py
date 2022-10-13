from weaviate import Client

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.weaviate.config import WEAVIATE_CLASS_NAME, WEAVIATE_DEFAULT_PORT


class WeaviateConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "l2-squared",
        Distance.COSINE: "cosine",
        Distance.DOT: "dot",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        url = f"http://{host}:{connection_params.pop('port', WEAVIATE_DEFAULT_PORT)}"
        self.client = Client(url, **connection_params)

    def clean(self):
        classes = self.client.schema.get()
        for cl in classes["classes"]:
            if cl["class"] == WEAVIATE_CLASS_NAME:
                self.client.schema.delete_class(WEAVIATE_CLASS_NAME)

    def recreate(self, dataset: Dataset, collection_params):
        self.client.schema.create_class(
            {
                "class": WEAVIATE_CLASS_NAME,
                "vectorizer": "none",
                "properties": [],
                "vectorIndexConfig": {
                    **{
                        "vectorCacheMaxObjects": 1000000000,
                        "distance": self.DISTANCE_MAPPING.get(dataset.config.distance),
                    },
                    **collection_params["vectorIndexConfig"],
                },
            }
        )
