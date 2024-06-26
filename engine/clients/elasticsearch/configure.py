from elasticsearch import NotFoundError

from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.elasticsearch.config import ELASTIC_INDEX, get_es_client


class ElasticConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "l2_norm",
        Distance.COSINE: "cosine",
        Distance.DOT: "dot_product",
    }
    INDEX_TYPE_MAPPING = {
        "int": "long",
        "keyword": "keyword",
        "text": "text",
        "float": "double",
        "geo": "geo_point",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self.client = get_es_client(host, connection_params)

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

        self.client.indices.create(
            index=ELASTIC_INDEX,
            settings={
                "index": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "refresh_interval": -1,  # no refresh is required because we index all the data at once
                }
            },
            mappings={
                "_source": {"excludes": ["vector"]},
                "properties": {
                    "vector": {
                        "type": "dense_vector",
                        "dims": dataset.config.vector_size,
                        "index": True,
                        "similarity": self.DISTANCE_MAPPING[dataset.config.distance],
                        "index_options": {
                            "type": "hnsw",
                            **collection_params["index_options"],
                        },
                    },
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
