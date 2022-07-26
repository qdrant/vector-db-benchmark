from weaviate import Client

from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance


class WeaviateConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2_SQUARED: "l2-squared",
        Distance.COSINE: "cosine",
        Distance.DOT: "dot",
    }

    def __init__(self, url):
        super().__init__()
        self.client = Client(url)

    def clean(self, collection_name):
        classes = self.client.schema.get()
        for cl in classes["classes"]:
            if cl["class"] == collection_name:
                self.client.schema.delete_class(collection_name)

    def recreate(self, collection_name, ef_construction, max_connections, distance, _):
        schema = self.read_default_config()
        schema["class"] = collection_name
        schema["vectorIndexConfig"]["efConstruction"] = ef_construction
        schema["vectorIndexConfig"]["maxConnections"] = max_connections
        self.client.schema.create_class(schema)
