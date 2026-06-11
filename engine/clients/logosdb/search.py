import json
from typing import List, Tuple

import numpy as np

from dataset_reader.base_reader import Query
from engine.base_client.search import BaseSearcher

DEFAULT_PATH = "/tmp/logosdb_vdb_bench"


class LogosDBSearcher(BaseSearcher):
    client = None

    @classmethod
    def init_client(
        cls, host: str, distance, connection_params: dict, search_params: dict
    ):
        import logosdb

        path = connection_params.get("path", DEFAULT_PATH)
        with open(path + ".meta.json") as f:
            meta = json.load(f)
        cls.client = logosdb.DB(
            path,
            dim=meta["dim"],
            distance=meta["distance"],
            max_elements=meta.get("max_elements", 2_000_000),
        )

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        q = np.array(query.vector, dtype=np.float32)
        hits = cls.client.search(q, top_k=top)
        return [(int(h.text), h.score) for h in hits]

    @classmethod
    def delete_client(cls):
        if cls.client is not None:
            del cls.client
            cls.client = None
