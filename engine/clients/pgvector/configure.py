import psycopg2
from elasticsearch import Elasticsearch, NotFoundError
from psycopg2.extras import RealDictCursor

from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.pgvector.config import get_db_config


class PgVectorConfigurator(BaseConfigurator):
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
        self.conn = psycopg2.connect(**get_db_config(host))
        self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)

    def clean(self):
        try:
            self.cursor.execute(
                "DROP TABLE IF EXISTS items CASCADE;",
            )
            self.conn.commit()
        except NotFoundError:
            pass

    def recreate(self, dataset: Dataset, collection_params):
        if dataset.config.distance == Distance.DOT:
            raise IncompatibilityError
        if dataset.config.vector_size > 1024:
            raise IncompatibilityError

        self.cursor.execute(
            f"""CREATE TABLE items (
                id SERIAL PRIMARY KEY,
                embedding vector({dataset.config.vector_size}) NOT NULL
            );"""
        )

        if dataset.config.distance == "cosine":
            hnsw_distance_type = "vector_cosine_ops"
        elif dataset.config.distance == "euclidean":
            hnsw_distance_type = "vector_l2_ops"
        else:
            raise NotImplementedError(f"Unsupported distance metric: {self.metric}")

        # FIXME: Shouldn't be hardcoded
        collection_params.update({"m": 16, "ef": 100})

        self.cursor.execute(
            f"CREATE INDEX on items USING hnsw(embedding {hnsw_distance_type}) WITH (m = {collection_params['m']}, ef_construction = {collection_params['ef']})"
        )
        self.conn.commit()
