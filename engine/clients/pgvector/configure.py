import psycopg2
from psycopg2.extras import RealDictCursor

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
        self.conn = psycopg2.connect(**get_db_config(host, connection_params))
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)

    def clean(self):
        self.cur.execute(
            "DROP TABLE IF EXISTS items CASCADE;",
        )
        self.conn.commit()

    def recreate(self, dataset: Dataset, collection_params):
        if dataset.config.distance == Distance.DOT:
            raise IncompatibilityError

        self.cur.execute(
            f"""CREATE TABLE items (
                id SERIAL PRIMARY KEY,
                embedding vector({dataset.config.vector_size}) NOT NULL
            );"""
        )
        self.cur.execute("ALTER TABLE items ALTER COLUMN embedding SET STORAGE PLAIN")

        try:
            hnsw_distance_type = self.DISTANCE_MAPPING[dataset.config.distance]
        except KeyError:
            raise IncompatibilityError(
                f"Unsupported distance metric: {dataset.config.distance}"
            )

        self.cur.execute(
            f"CREATE INDEX on items USING hnsw(embedding {hnsw_distance_type}) WITH (m = {collection_params['hnsw_config']['m']}, ef_construction = {collection_params['hnsw_config']['ef_construct']})"
        )
        self.conn.commit()

        self.cur.close()
        self.conn.close()
