import multiprocessing as mp
import uuid
from typing import List

import backoff
from opensearchpy import OpenSearch
from opensearchpy.exceptions import TransportError

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.opensearch.config import (
    OPENSEARCH_INDEX,
    OPENSEARCH_BULK_INDEX_TIMEOUT,
    OPENSEARCH_FULL_INDEX_TIMEOUT,
    _wait_for_es_status,
    get_opensearch_client,
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
        cls.client = get_opensearch_client(host, connection_params)
        cls.upload_params = upload_params

    def _upload_backoff_handler(details):
        print(
            f"Backing off OpenSearch bulk upload for {details['wait']} seconds after {details['tries']} tries due to {details['exception']}"
        )

    def _index_backoff_handler(details):
        print(
            f"Backing off OpenSearch indexing for {details['wait']} seconds after {details['tries']} tries due to {details['exception']}"
        )

    @classmethod
    @backoff.on_exception(
        backoff.expo,
        TransportError,
        max_time=OPENSEARCH_FULL_INDEX_TIMEOUT,
        on_backoff=_upload_backoff_handler,
    )
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
                "timeout": OPENSEARCH_BULK_INDEX_TIMEOUT,
            },
        )

    @classmethod
    @backoff.on_exception(
        backoff.expo,
        TransportError,
        max_time=OPENSEARCH_FULL_INDEX_TIMEOUT,
        on_backoff=_index_backoff_handler,
    )
    def post_upload(cls, _distance):
        print(
            "Updated the index settings back to the default and waiting for indexing to be completed."
        )
        # Update the index settings back to the default
        refresh_interval = "1s"
        cls.client.indices.put_settings(
            index=OPENSEARCH_INDEX,
            body={"index": {"refresh_interval": refresh_interval}},
        )
        _wait_for_es_status(cls.client)
        return {}

    def get_memory_usage(cls):
        index_stats = cls.client.indices.stats(index=OPENSEARCH_INDEX)
        size_in_bytes = index_stats["_all"]["primaries"]["store"]["size_in_bytes"]
        return {
            "size_in_bytes": size_in_bytes,
            "index_info": index_stats,
        }
