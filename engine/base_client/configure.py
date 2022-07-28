from typing import Optional


class BaseConfigurator:
    DISTANCE_MAPPING = {}

    def __init__(self, host, collection_params: dict, connection_params: dict):
        self.host = host
        self.collection_params = collection_params
        self.connection_params = connection_params

    def clean(self):
        raise NotImplementedError()

    def recreate(self, distance, vector_size, collection_params):
        raise NotImplementedError()

    def configure(self, distance, vector_size) -> Optional[dict]:
        self.clean()
        return self.recreate(distance, vector_size, self.collection_params) or {}
