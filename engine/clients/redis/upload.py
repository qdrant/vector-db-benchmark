from typing import List

import numpy as np
from redis import Redis, RedisCluster

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.redis.config import (
    REDIS_AUTH,
    REDIS_CLUSTER,
    REDIS_PORT,
    REDIS_USER,
)
from engine.clients.redis.helper import convert_to_redis_coords


class RedisUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        redis_constructor = RedisCluster if REDIS_CLUSTER else Redis
        cls.client = redis_constructor(
            host=host, port=REDIS_PORT, password=REDIS_AUTH, username=REDIS_USER
        )
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        p = cls.client.pipeline(transaction=False)
        for record in batch:
            idx = record.id
            vec = record.vector
            meta = record.metadata or {}
            geopoints = {}
            payload = {}
            if meta is not None:
                for k, v in meta.items():
                    # This is a patch for arxiv-titles dataset where we have a list of "labels", and
                    # we want to index all of them under the same TAG field (whose separator is ';').
                    if k == "labels":
                        payload[k] = ";".join(v)
                    if (
                        v is not None
                        and not isinstance(v, dict)
                        and not isinstance(v, list)
                    ):
                        payload[k] = v
                # Redis treats geopoints differently and requires putting them as
                # a comma-separated string with lat and lon coordinates
                geopoints = {
                    k: ",".join(map(str, convert_to_redis_coords(v["lon"], v["lat"])))
                    for k, v in meta.items()
                    if isinstance(v, dict)
                }
            cls.client.hset(
                str(idx),
                mapping={
                    "vector": np.array(vec).astype(np.float32).tobytes(),
                    **payload,
                    **geopoints,
                },
            )
        p.execute()

    @classmethod
    def post_upload(cls, _distance):
        return {}
