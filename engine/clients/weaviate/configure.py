from weaviate import WeaviateClient
from weaviate.connect import ConnectionParams

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
    FIELD_TYPE_MAPPING = {
        "int": "int",
        "keyword": "string",
        "text": "string",
        "float": "number",
        "geo": "geoCoordinates",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        url = f"http://{host}:{connection_params.get('port', WEAVIATE_DEFAULT_PORT)}"
        client = WeaviateClient(
            ConnectionParams.from_url(url, 50051), skip_init_checks=True
        )
        client.connect()
        self.client = client

    def clean(self):
        self.client.collections.delete(WEAVIATE_CLASS_NAME)

    def recreate(self, dataset: Dataset, collection_params):
        self.client.collections.create_from_dict(
            {
                "class": WEAVIATE_CLASS_NAME,
                "vectorizer": "none",
                "properties": [
                    {
                        "name": field_name,
                        "dataType": [
                            self.FIELD_TYPE_MAPPING[field_type],
                        ],
                        "indexInverted": True,
                    }
                    for field_name, field_type in dataset.config.schema.items()
                ],
                "vectorIndexConfig": {
                    **{
                        "vectorCacheMaxObjects": 1000000000,
                        "distance": self.DISTANCE_MAPPING.get(dataset.config.distance),
                    },
                    **collection_params["vectorIndexConfig"],
                },
            }
        )
        self.client.close()

    def __del__(self):
        if self.client.is_connected():
            self.client.close()
