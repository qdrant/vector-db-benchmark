import uuid
from typing import Optional, List

from elasticsearch import Elasticsearch

from engine.base_client.upload import BaseUploader
from engine.clients.elasticsearch import ELASTIC_PORT, ELASTIC_USER, ELASTIC_PASSWORD, ELASTIC_INDEX


class ElasticUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, connection_params, upload_params):
        cls.client: Elasticsearch = Elasticsearch(
            f"http://{host}:{ELASTIC_PORT}",
            basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
            **{
                **{
                    "verify_certs": False,
                    "request_timeout": 90,
                    "retry_on_timeout": True,
                },
                **connection_params
            }
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
        cls.client.indices.forcemerge(
            index=ELASTIC_INDEX,
            wait_for_completion=True
        )
        return {}
