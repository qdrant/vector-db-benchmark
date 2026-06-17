import time
from collections import defaultdict
from typing import Iterable, List

import tqdm
import turbopuffer as tpuf

from dataset_reader.base_reader import Record
from engine.base_client.distances import Distance
from engine.base_client.upload import BaseUploader
from engine.base_client.utils import iter_batches
from engine.clients.turbopuffer.config import (
    TURBOPUFFER_API_KEY,
    TURBOPUFFER_REGION,
    resolve_namespace,
)

DISTANCE_MAPPING = {
    Distance.COSINE: "cosine_distance",
    Distance.L2: "euclidean_squared",
}


class TurbopufferUploader(BaseUploader):
    client: tpuf.Turbopuffer = None
    namespace = None  # Namespace type
    namespaces: dict = {}  # tenant_value -> Namespace, used when namespace_field is set
    base_namespace: str = None
    namespace_field: str = None
    distance_metric: str = None
    upload_params = {}

    @classmethod
    def get_mp_start_method(cls):
        return "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, upload_params: dict):
        api_key = connection_params.get("api_key", TURBOPUFFER_API_KEY)
        region = connection_params.get("region", TURBOPUFFER_REGION)
        cls.client = tpuf.Turbopuffer(api_key=api_key, region=region)
        cls.namespace_field = connection_params.get("namespace_field")
        cls.base_namespace = resolve_namespace(connection_params)
        cls.namespaces = {}
        if cls.namespace_field:
            cls.namespace = None
        else:
            cls.namespace = cls.client.namespace(cls.base_namespace)
        cls.distance_metric = DISTANCE_MAPPING[distance]
        cls.upload_params = upload_params

    @classmethod
    def _get_tenant_namespace(cls, tenant_value: str):
        if tenant_value not in cls.namespaces:
            cls.namespaces[tenant_value] = cls.client.namespace(
                f"{cls.base_namespace}-{tenant_value}"
            )
        return cls.namespaces[tenant_value]

    def upload(self, distance, records: Iterable[Record]) -> dict:
        # For namespace-per-tenant mode: buffer per-tenant and flush each tenant
        # when its buffer hits batch_size. Max memory = num_tenants * batch_size
        # records, not all 1M at once.
        if not self.connection_params.get("namespace_field"):
            return super().upload(distance, records)

        self.init_client(self.host, distance, self.connection_params, self.upload_params)
        batch_size = self.upload_params.get("batch_size", 1000)
        latencies = []
        start = time.perf_counter()

        tenant_field = self.connection_params["namespace_field"]
        buffers: dict = defaultdict(list)

        for record in tqdm.tqdm(records, desc="Uploading"):
            tenant = record.metadata.get(tenant_field) if record.metadata else None
            buffers[tenant].append(record)
            if len(buffers[tenant]) >= batch_size:
                latencies.append(self._upload_batch(buffers.pop(tenant)))

        # Flush remaining partial batches
        for tenant_records in buffers.values():
            for batch in iter_batches(tenant_records, batch_size):
                latencies.append(self._upload_batch(batch))

        upload_time = time.perf_counter() - start
        print(f"Upload time: {upload_time}")
        print("Experiment stage: Post-upload")
        post_upload_stats = self.post_upload(distance)
        total_time = time.perf_counter() - start
        print(f"Total import time: {total_time}")
        self.delete_client()
        return {
            "post_upload": post_upload_stats,
            "upload_time": upload_time,
            "total_time": total_time,
            "latencies": latencies,
        }

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        if cls.namespace_field:
            # Partition batch by tenant field and write to per-tenant namespaces
            partitions: dict = {}
            for record in batch:
                tenant = record.metadata.get(cls.namespace_field) if record.metadata else None
                if tenant is None:
                    raise ValueError(f"Record {record.id} missing namespace_field '{cls.namespace_field}'")
                partitions.setdefault(tenant, []).append(record)

            for tenant_value, tenant_records in partitions.items():
                ids, vectors, attributes = [], [], {}
                for record in tenant_records:
                    ids.append(record.id)
                    vectors.append(record.vector)
                    # Still store the tenant field as an attribute for reference
                    if record.metadata:
                        for key, value in record.metadata.items():
                            attributes.setdefault(key, []).append(value)
                ns = cls._get_tenant_namespace(tenant_value)
                ns.write(
                    upsert_columns={"id": ids, "vector": vectors, **attributes},
                    distance_metric=cls.distance_metric,
                )
        else:
            ids = []
            vectors = []
            attributes = {}

            for record in batch:
                ids.append(record.id)
                vectors.append(record.vector)
                if record.metadata:
                    for key, value in record.metadata.items():
                        attributes.setdefault(key, []).append(value)

            upsert_columns = {"id": ids, "vector": vectors, **attributes}
            cls.namespace.write(
                upsert_columns=upsert_columns,
                distance_metric=cls.distance_metric,
            )

    @classmethod
    def delete_client(cls):
        cls.client = None
        cls.namespace = None
        cls.namespaces = {}
