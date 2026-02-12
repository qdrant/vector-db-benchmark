import multiprocessing as mp
import time
import uuid
from typing import List

from opensearchpy import OpenSearch

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.opensearch.config import (
    OPENSEARCH_INDEX,
    OPENSEARCH_PASSWORD,
    OPENSEARCH_PORT,
    OPENSEARCH_USER,
)
from engine.clients.opensearch.utils import (
    get_index_thread_qty_for_force_merge,
    update_force_merge_threads,
)


class ClosableOpenSearch(OpenSearch):
    def __del__(self):
        self.close()


class OpenSearchUploader(BaseUploader):
    client: OpenSearch = None
    upload_params = {}

    @classmethod
    def get_mp_start_method(cls):
        return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        init_params = {
            **{
                "verify_certs": False,
                "request_timeout": 90,
                "retry_on_timeout": True,
            },
            **connection_params,
        }
        cls.client = OpenSearch(
            f"http://{host}:{OPENSEARCH_PORT}",
            basic_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
            **init_params,
        )
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        operations = []
        for record in batch:
            vector_id = uuid.UUID(int=record.id).hex
            operations.append({"index": {"_id": vector_id}})
            operations.append({"vector": record.vector, **(record.metadata or {})})

        cls.client.bulk(
            index=OPENSEARCH_INDEX,
            body=operations,
            params={
                "timeout": 300,
            },
        )

    @classmethod
    def post_upload(cls, _distance):
        # ensuring that index is refreshed before force merge
        cls._refresh_index()
        cls._update_vector_threshold_setting()
        cls._force_merge_index()
        # ensuring that only force merged segments are remaining
        cls._refresh_index()
        return {}

    @classmethod
    def _refresh_index(cls):
        print(f"Refreshing index: {OPENSEARCH_INDEX}")
        params = {"timeout": 300}
        cls.client.indices.refresh(index=OPENSEARCH_INDEX, params=params)

    @classmethod
    def _update_vector_threshold_setting(cls):
        body = {
            # ensure that approximate graph creation is enabled
            "index.knn.advanced.approximate_threshold": "0"
        }
        cls.client.indices.put_settings(index=OPENSEARCH_INDEX, body=body)

    @classmethod
    def _force_merge_index(cls):
        index_thread_qty = get_index_thread_qty_for_force_merge(cls.client)
        update_force_merge_threads(client=cls.client, index_thread_qty=index_thread_qty)
        force_merge_endpoint = f"/{OPENSEARCH_INDEX}/_forcemerge?max_num_segments=1&wait_for_completion=false"
        force_merge_task_id = cls.client.transport.perform_request(
            "POST", force_merge_endpoint
        )["task"]
        SECONDS_WAITING_FOR_FORCE_MERGE_API_CALL_SEC = 30
        print(
            f"Starting force merge on index: {OPENSEARCH_INDEX}, task_id: {force_merge_task_id}"
        )
        while True:
            time.sleep(SECONDS_WAITING_FOR_FORCE_MERGE_API_CALL_SEC)
            task_status = cls.client.tasks.get(task_id=force_merge_task_id)
            if task_status["completed"]:
                break
