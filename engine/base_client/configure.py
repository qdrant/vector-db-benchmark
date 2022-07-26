import json
import time
from pathlib import Path


class BaseConfigurator:
    DEFAULT_CONFIG_PATH = Path("default.json")
    DISTANCE_MAPPING = {}

    def __init__(self, collection_params: dict):
        self.collection_params = collection_params

    def clean(self, collection_name):
        raise NotImplementedError()

    def recreate(
        self, collection_name, ef_construction, max_connections, distance, vector_size
    ):
        raise NotImplementedError()

    def configure(
        self, collection_name, ef_construction, max_connections, distance, vector_size
    ):
        collection_name = collection_name.replace("-", "_").capitalize()
        self.clean(collection_name)
        start = time.perf_counter()
        self.recreate(
            collection_name, ef_construction, max_connections, distance, vector_size
        )
        return time.perf_counter() - start

    @classmethod
    def read_default_config(cls):
        with open(cls.DEFAULT_CONFIG_PATH, "r") as fp:
            return json.load(fp)
