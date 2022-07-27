import json
import time
from pathlib import Path


class BaseConfigurator:
    DEFAULT_CONFIG_PATH = Path("default.json")
    DISTANCE_MAPPING = {}

    def __init__(self, host, collection_params: dict, connection_params: dict):
        self.host = host
        self.collection_params = collection_params
        self.connection_params = connection_params

    def clean(self):
        raise NotImplementedError()

    def recreate(self, distance, vector_size, collection_params):
        raise NotImplementedError()

    def configure(self, distance, vector_size):
        self.clean()
        start = time.perf_counter()
        self.recreate(distance, vector_size, self.collection_params)
        return time.perf_counter() - start

    @classmethod
    def read_default_config(cls):
        with open(cls.DEFAULT_CONFIG_PATH, "r") as fp:
            return json.load(fp)
