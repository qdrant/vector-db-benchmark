from elasticsearch import Elasticsearch, NotFoundError

from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.elasticsearch import (
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

    def recreate(
        self,
        distance,
        vector_size,
        collection_params,
    ):
        if distance == Distance.DOT:
            raise IncompatibilityError

        self.client.indices.create(
            index=ELASTIC_INDEX,
            mappings={
                "properties": {
                    "vector": {
                        "type": "dense_vector",
                        "dims": vector_size,
                        "index": True,
                        "similarity": self.DISTANCE_MAPPING[distance],
                        "index_options": {
                            **{
                                "type": "hnsw",
                                "m": 16,
                                "ef_construction": 100,
                            },
                            **collection_params.get("index_options"),
                        },
                    }
                }
            },
        )
