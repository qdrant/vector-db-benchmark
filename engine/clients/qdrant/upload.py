import os
import time
from typing import List

from qdrant_client import QdrantClient
from qdrant_client._pydantic_compat import construct
from qdrant_client.http.models import (
    Batch,
    CollectionStatus,
    OptimizersConfigDiff,
    SparseVector,
)

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.qdrant.config import QDRANT_COLLECTION_NAME


class QdrantUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "true"
        os.environ["GRPC_POLL_STRATEGY"] = "epoll,poll"
        cls.client = QdrantClient(host=host, prefer_grpc=True, **connection_params)
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        ids, vectors, payloads = [], [], []
        for point in batch:
            if point.sparse_vector is None:
                vector = point.vector
            else:
                vector = {
                    "sparse": construct(
                        SparseVector,
                        indices=point.sparse_vector.indices,
                        values=point.sparse_vector.values,
                    )
                }

            ids.append(point.id)
            vectors.append(vector)
            payloads.append(point.metadata or {})

        _ = cls.client.upsert(
            collection_name=QDRANT_COLLECTION_NAME,
            points=Batch.model_construct(
                ids=ids,
                vectors=vectors,
                payloads=payloads,
            ),
            wait=False,
        )

    @classmethod
    def post_upload(cls, _distance):
        cls.client.update_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            optimizer_config=OptimizersConfigDiff(
                # indexing_threshold=10_000,
                max_optimization_threads=1,
            ),
        )

        cls.wait_collection_green()
        return {}

    @classmethod
    def wait_collection_green(cls):
        wait_time = 5.0
        total = 0
        while True:
            time.sleep(wait_time)
            total += wait_time
            collection_info = cls.client.get_collection(QDRANT_COLLECTION_NAME)
            if collection_info.status != CollectionStatus.GREEN:
                continue
            time.sleep(wait_time)
            collection_info = cls.client.get_collection(QDRANT_COLLECTION_NAME)
            if collection_info.status == CollectionStatus.GREEN:
                break
        return total

    @classmethod
    def delete_client(cls):
        if cls.client is not None:
            del cls.client
