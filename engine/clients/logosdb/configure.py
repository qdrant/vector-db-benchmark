import json
import os
import shutil

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance

DISTANCE_MAP = {
    Distance.COSINE: 1,  # logosdb.DIST_COSINE
    Distance.DOT: 0,     # logosdb.DIST_IP
    Distance.L2: 2,      # logosdb.DIST_L2
}

DEFAULT_PATH = "/tmp/logosdb_vdb_bench"


class LogosDBConfigurator(BaseConfigurator):
    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self.path = connection_params.get("path", DEFAULT_PATH)

    def clean(self):
        if os.path.exists(self.path):
            shutil.rmtree(self.path)
        meta = self.path + ".meta.json"
        if os.path.exists(meta):
            os.remove(meta)

    def recreate(self, dataset: Dataset, collection_params):
        import logosdb

        dim = dataset.config.vector_size
        dist = DISTANCE_MAP.get(dataset.config.distance, logosdb.DIST_COSINE)
        max_elements = collection_params.get("max_elements", 2_000_000)

        db = logosdb.DB(self.path, dim=dim, distance=dist, max_elements=max_elements)
        del db

        with open(self.path + ".meta.json", "w") as f:
            json.dump({"dim": dim, "distance": int(dist), "max_elements": max_elements}, f)

        return {}
