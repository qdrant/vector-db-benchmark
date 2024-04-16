import pgvector.psycopg
import psycopg

from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.pgvector.config import get_db_config


class PgVectorConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "vector_l2_ops",
        Distance.COSINE: "vector_cosine_ops",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self.conn = psycopg.connect(**get_db_config(host, connection_params))
        print("configure connection created")
        self.conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        pgvector.psycopg.register_vector(self.conn)

    def clean(self):
        self.conn.execute(
            "DROP TABLE IF EXISTS items CASCADE;",
        )

    def recreate(self, dataset: Dataset, collection_params):
        if dataset.config.distance == Distance.DOT:
            raise IncompatibilityError

        self.conn.execute(
            f"""CREATE TABLE items (
                id SERIAL PRIMARY KEY,
                embedding vector({dataset.config.vector_size}) NOT NULL
            );"""
        )
        self.conn.execute("ALTER TABLE items ALTER COLUMN embedding SET STORAGE PLAIN")

        try:
            hnsw_distance_type = self.DISTANCE_MAPPING[dataset.config.distance]
        except KeyError:
            raise IncompatibilityError(
                f"Unsupported distance metric: {dataset.config.distance}"
            )

        self.conn.execute(
            f"CREATE INDEX on items USING hnsw(embedding {hnsw_distance_type}) WITH "
            f"(m = {collection_params['hnsw_config']['m']}, "
            f"ef_construction = {collection_params['hnsw_config']['ef_construct']})"
        )

        self.conn.close()

    def delete_client(self):
        self.conn.close()
