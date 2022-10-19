import redis
from redis.commands.search.field import VectorField

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.redis.config import FIELD_MAPPING, REDIS_PORT


class RedisConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "L2",
        Distance.COSINE: "COSINE",
        Distance.DOT: "IP",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)

        self.client = redis.Redis(host=host, port=REDIS_PORT, db=0)

    def clean(self):
        index = self.client.ft()
        try:
            index.dropindex(delete_documents=True)
        except redis.ResponseError as e:
            print(e)

    def recreate(self, dataset: Dataset, collection_params):
        self.clean()
        search_namespace = self.client.ft()
        payload_fields = [
            FIELD_MAPPING[field_type](
                name=field_name,
            )
            for field_name, field_type in dataset.config.schema.items()
        ]
        search_namespace.create_index(
            fields=[
                VectorField(
                    name="vector",
                    algorithm="HNSW",
                    attributes={
                        "TYPE": "FLOAT32",
                        "DIM": dataset.config.vector_size,
                        "DISTANCE_METRIC": self.DISTANCE_MAPPING[
                            dataset.config.distance
                        ],
                        **self.collection_params.get("hnsw_config", {}),
                    },
                )
            ]
            + payload_fields
        )


if __name__ == "__main__":
    pass
