import psycopg
from pgvector.psycopg import register_vector

from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.pgvector.config import PGVECTOR_COLLECTION_NAME


class PgvectorConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "l2_distance",
        Distance.COSINE: "cosine_distance",
        Distance.DOT: "inner_product",
    }
    FIELD_MAPPING = {
        "int": "integer",
        "keyword": "varchar",
        "text": "text",
        "float": "real",
        "geo": "point",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self.client = psycopg.connect(host, **connection_params)
        register_vector(self.client)
        print("established connection")

    def clean(self):
        with self.client.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {PGVECTOR_COLLECTION_NAME}")

    def recreate(self, dataset: Dataset, collection_params):
        if dataset.config.vector_size > 1536:
            raise IncompatibilityError

        fields = [
            f'"{field_name}" {self.FIELD_MAPPING.get(field_type)}'
            for field_name, field_type in dataset.config.schema.items()
        ]

        with self.client.cursor() as cur:
            create_stmt = f"""
                CREATE TABLE IF NOT EXISTS {PGVECTOR_COLLECTION_NAME} (
                    id serial PRIMARY KEY,
                    "vector" vector({dataset.config.vector_size}),
                """
            create_stmt += ', '.join(fields)
            create_stmt += ")"
            cur.execute(create_stmt)
