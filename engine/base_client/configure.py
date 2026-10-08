
from benchmark.dataset import Dataset


class BaseConfigurator:
    SPARSE_VECTOR_SUPPORT: bool = False
    DISTANCE_MAPPING = {}

    def __init__(self, host, collection_params: dict, connection_params: dict):
        self.host = host
        self.collection_params = collection_params
        self.connection_params = connection_params

    def clean(self):
        raise NotImplementedError()

    def recreate(self, dataset: Dataset, collection_params):
        raise NotImplementedError()

    def configure(self, dataset: Dataset) -> dict | None:
        self.clean()
        return self.recreate(dataset, self.collection_params) or {}

    def execution_params(self, distance, vector_size) -> dict:
        return {}

    def delete_client(self):
        pass
