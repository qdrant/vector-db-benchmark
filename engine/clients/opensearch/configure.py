from opensearchpy import NotFoundError, OpenSearch

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.opensearch.config import (
    OPENSEARCH_INDEX,
    OPENSEARCH_PASSWORD,
    OPENSEARCH_PORT,
    OPENSEARCH_USER,
)
from engine.clients.opensearch.utils import get_index_thread_qty


class OpenSearchConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "l2",
        Distance.COSINE: "cosinesimil",
        Distance.DOT: "innerproduct",
    }
    INDEX_TYPE_MAPPING = {
        "int": "long",
        "geo": "geo_point",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        init_params = {
            **{
                "verify_certs": False,
                "request_timeout": 90,
                "retry_on_timeout": True,
            },
            **connection_params,
        }
        self.client = OpenSearch(
            f"http://{host}:{OPENSEARCH_PORT}",
            basic_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
            **init_params,
        )

    def clean(self):
        is_index_available = self.client.indices.exists(index=OPENSEARCH_INDEX,
            params={
                "timeout": 300,
            })
        if(is_index_available):
            print(f"Deleting index: {OPENSEARCH_INDEX}, as it is already present")
            self.client.indices.delete(
                index=OPENSEARCH_INDEX,
                params={
                    "timeout": 300,
                },
            )
        

    def recreate(self, dataset: Dataset, collection_params):
        self._update_cluster_settings()
        distance = self.DISTANCE_MAPPING[dataset.config.distance]
        if dataset.config.distance == Distance.COSINE:
            distance = self.DISTANCE_MAPPING[Distance.DOT]
            print(f"Using distance type: {distance} as dataset distance is : {dataset.config.distance}")

        self.client.indices.create(
            index=OPENSEARCH_INDEX,
            body={
                "settings": {
                    "index": {
                        "knn": True,
                        "refresh_interval": -1,
                        "number_of_replicas": 0 if collection_params.get("number_of_replicas") == None else collection_params.get("number_of_replicas"),
                        "number_of_shards": 1 if collection_params.get("number_of_shards") == None else collection_params.get("number_of_shards"),
                        "knn.advanced.approximate_threshold": "-1"
                    }
                },
                "mappings": {
                    "properties": {
                        "vector": {
                            "type": "knn_vector",
                            "dimension": dataset.config.vector_size,
                            "method": {
                                **{
                                    "name": "hnsw",
                                    "engine": "faiss",
                                    "space_type": distance,
                                    **collection_params.get("method")
                                },
                            },
                        },
                        # this doesn't work for nmslib, we need see what to do here, may be remove them
                        **self._prepare_fields_config(dataset),
                    }
                },
            },
            params={
                "timeout": 300,
            },
            cluster_manager_timeout="5m",
        )

    def _update_cluster_settings(self):
        index_thread_qty = get_index_thread_qty(self.client)
        cluster_settings_body = {
            "persistent": {
                "knn.memory.circuit_breaker.limit": "75%", # putting a higher value to ensure that even with small cluster the latencies for vector search are good
                "knn.algo_param.index_thread_qty": index_thread_qty
            }
        }
        self.client.cluster.put_settings(cluster_settings_body)

    def _prepare_fields_config(self, dataset: Dataset):
        return {
            field_name: {
                # The mapping is used only for several types, as some of them
                # overlap with the ones used internally.
                "type": self.INDEX_TYPE_MAPPING.get(field_type, field_type),
                "index": True,
            }
            for field_name, field_type in dataset.config.schema.items()
        }
    
    def execution_params(self, distance, vector_size) -> dict:
        # normalize the vectors if cosine similarity is there.
        if distance == Distance.COSINE:
            return {"normalize": "true"}
        return {}
