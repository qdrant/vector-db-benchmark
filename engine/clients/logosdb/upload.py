import json
from typing import List

import numpy as np

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader

DEFAULT_PATH = "/tmp/logosdb_vdb_bench"


class LogosDBUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, upload_params: dict):
        import logosdb

        path = connection_params.get("path", DEFAULT_PATH)
        with open(path + ".meta.json") as f:
            meta = json.load(f)
        cls.client = logosdb.DB(path, dim=meta["dim"], distance=meta["distance"], max_elements=meta.get("max_elements", 2_000_000))
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        vectors = np.array([r.vector for r in batch], dtype=np.float32)
        texts = [str(r.id) for r in batch]
        cls.client.put_batch(vectors, texts=texts)

    @classmethod
    def post_upload(cls, distance):
        return {}

    @classmethod
    def delete_client(cls):
        if cls.client is not None:
            del cls.client
            cls.client = None
