import multiprocessing as mp
import uuid
from typing import List

from elasticsearch import Elasticsearch

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.elasticsearch.config import ELASTIC_INDEX, get_es_client


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
    def upload_batch(cls, batch: List[Record]):
        operations = []
        for record in batch:
            vector_id = uuid.UUID(int=record.id).hex
            operations.append({"index": {"_id": vector_id}})
            operations.append({"vector": record.vector, **(record.metadata or {})})

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
