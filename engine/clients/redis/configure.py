import redis
from redis import Redis, RedisCluster
from redis.commands.search.field import (
    GeoField,
    NumericField,
    TagField,
    TextField,
    VectorField,
)

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.redis.config import (
    REDIS_AUTH,
    REDIS_CLUSTER,
    REDIS_PORT,
    REDIS_USER,
)


class RedisConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "L2",
        Distance.COSINE: "COSINE",
        Distance.DOT: "IP",
    }
    FIELD_MAPPING = {
        "int": NumericField,
        "keyword": TagField,
        "text": TextField,
        "float": NumericField,
        "geo": GeoField,
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        redis_constructor = RedisCluster if REDIS_CLUSTER else Redis
        self.is_cluster = REDIS_CLUSTER
        self.client = redis_constructor(
            host=host, port=REDIS_PORT, password=REDIS_AUTH, username=REDIS_USER
        )

    def clean(self):
        conns = [self.client]
        if self.is_cluster:
            conns = [
                self.client.get_redis_connection(node)
                for node in self.client.get_primaries()
            ]
        for conn in conns:
            search_namespace = conn.ft()
            try:
                search_namespace.dropindex(delete_documents=True)
            except redis.ResponseError as e:
                if "Unknown Index name" not in str(e):
                    print(e)

    def recreate(self, dataset: Dataset, collection_params):
        self.clean()

        payload_fields = [
            self.FIELD_MAPPING[field_type](
                name=field_name,
                sortable=True,
            )
            for field_name, field_type in dataset.config.schema.items()
            if field_type != "keyword"
        ]
        payload_fields += [
            TagField(
                name=field_name,
                separator=";",
                sortable=True,
            )
            for field_name, field_type in dataset.config.schema.items()
            if field_type == "keyword"
        ]
        index_fields = [
            VectorField(
                name="vector",
                algorithm="HNSW",
                attributes={
                    "TYPE": "FLOAT32",
                    "DIM": dataset.config.vector_size,
                    "DISTANCE_METRIC": self.DISTANCE_MAPPING[dataset.config.distance],
                    **self.collection_params.get("hnsw_config", {}),
                },
            )
        ] + payload_fields

        conns = [self.client]
        if self.is_cluster:
            conns = [
                self.client.get_redis_connection(node)
                for node in self.client.get_primaries()
            ]
        for conn in conns:
            search_namespace = conn.ft()
            try:
                search_namespace.create_index(fields=index_fields)
            except redis.ResponseError as e:
                if "Index already exists" not in str(e):
                    raise e


if __name__ == "__main__":
    pass
