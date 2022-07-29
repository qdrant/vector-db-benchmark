import uuid
import multiprocessing as mp
from typing import List, Optional

from elasticsearch import Elasticsearch

from engine.base_client.upload import BaseUploader
from engine.clients.elasticsearch import (
    ELASTIC_INDEX,
    ELASTIC_PASSWORD,
    ELASTIC_PORT,
    ELASTIC_USER,
)


class ClosableElastic(Elasticsearch):

    def __del__(self):
        self.close()


class ElasticUploader(BaseUploader):
    client: Elasticsearch = None
    upload_params = {}

    @classmethod
    def get_mp_start_method(cls):
        return 'forkserver' if 'forkserver' in mp.get_all_start_methods() else 'spawn'

    @classmethod
    def init_client(cls, host, connection_params, upload_params):
        init_params = {
            **{
                "verify_certs": False,
                "request_timeout": 90,
                "retry_on_timeout": True,
            },
            **connection_params,
        }
        cls.client = Elasticsearch(
            f"http://{host}:{ELASTIC_PORT}",
            basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
            **init_params,
        )
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(
        cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]
    ):
        operations = []
        for idx, vector in zip(ids, vectors):
            vector_id = uuid.UUID(int=idx).hex

            operations.append({"index": {"_id": vector_id}})
            operations.append({"vector": vector})

        cls.client.bulk(
            index=ELASTIC_INDEX,
            operations=operations,
        )

    @classmethod
    def post_upload(cls):
        cls.client.indices.forcemerge(index=ELASTIC_INDEX, wait_for_completion=True)
        return {}
