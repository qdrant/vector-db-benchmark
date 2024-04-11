import multiprocessing as mp
import uuid
from typing import List, Optional

from elasticsearch import Elasticsearch

from engine.base_client.upload import BaseUploader
from engine.clients.elasticsearch.config import get_es_client
from engine.clients.elasticsearch.config import (
    ELASTIC_INDEX,
)

class ClosableElastic(Elasticsearch):
    def __del__(self):
        self.close()


class ElasticUploader(BaseUploader):
    client: Elasticsearch = None
    upload_params = {}

    @classmethod
    def get_mp_start_method(cls):
        return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def init_client(cls, host, _distance, connection_params, upload_params):
        cls.client = get_es_client(host, connection_params)
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(
        cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]
    ):
        if metadata is None:
            metadata = [{}] * len(vectors)
        operations = []
        for idx, vector, payload in zip(ids, vectors, metadata):
            vector_id = uuid.UUID(int=idx).hex
            operations.append({"index": {"_id": vector_id}})
            if payload:
                operations.append({"vector": vector, **payload})
            else:
                operations.append({"vector": vector})

        cls.client.bulk(
            index=ELASTIC_INDEX,
            operations=operations,
        )

    @classmethod
    def post_upload(cls, _distance):
        cls.client.indices.forcemerge(
            index=ELASTIC_INDEX, wait_for_completion=True, max_num_segments=1
        )
        return {}
