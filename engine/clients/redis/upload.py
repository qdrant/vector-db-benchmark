from typing import List, Optional

import numpy as np
import redis

from engine.base_client.upload import BaseUploader
from engine.clients.redis.config import REDIS_PORT


class RedisUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.client = redis.Redis(host=host, port=REDIS_PORT, db=0)
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(
        cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]
    ):
        p = cls.client.pipeline(transaction=False)
        for i in range(len(ids)):
            idx = ids[i]
            vec = vectors[i]
            meta = metadata[i] if metadata else {}
            meta = meta or {}
            cls.client.hset(str(idx), mapping={
                "vector": np.array(vec).astype(np.float32).tobytes(),
                **meta
            })
        p.execute()

    @classmethod
    def post_upload(cls, _distance):
        return {}


