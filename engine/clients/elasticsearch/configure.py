from elasticsearch import Elasticsearch, NotFoundError

from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.elasticsearch.config import (
    ELASTIC_INDEX,
    ELASTIC_PASSWORD,
    ELASTIC_PORT,
    ELASTIC_USER,
)


class ElasticConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "l2_norm",
        Distance.COSINE: "cosine",
        Distance.DOT: "dot_product",
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
        self.client = Elasticsearch(
            f"http://{host}:{ELASTIC_PORT}",
            basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
            **init_params,
        )

    def clean(self):
        try:
            self.client.indices.delete(
                index=ELASTIC_INDEX, timeout="5m", master_timeout="5m"
            )
        except NotFoundError:
            pass

    def recreate(self, dataset: Dataset, collection_params):
        if dataset.config.distance == Distance.DOT:
            raise IncompatibilityError
        if dataset.config.vector_size > 2048:
            # https://www.elastic.co/guide/en/elasticsearch/reference/8.10/dense-vector.html#dense-vector-params
            raise IncompatibilityError
        index = collection_params["index"] if "index" in collection_params else True
        vector_mapping = {
            "type": "dense_vector",
            "dims": dataset.config.vector_size,
            "index": index,
        }

        if index:
            vector_mapping["similarity"] = self.DISTANCE_MAPPING[dataset.config.distance]
            vector_mapping["index_options"] = {
                **{
                    "type": "hnsw",
                    "m": 16,
                    "ef_construction": 100,
                },
                **collection_params.get("index_options"),
            }

        self.client.indices.create(
            index=ELASTIC_INDEX,
            settings={
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "refresh_interval": -1,
                }
            },
            mappings={
                "_source": {"excludes": ["vector"]},
                "properties": {
                    "vector": vector_mapping,
                    **self._prepare_fields_config(dataset),
                },
            },
        )

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
