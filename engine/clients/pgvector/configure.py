import pgvector.psycopg
import psycopg

from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.pgvector.config import PAYLOAD_SQL_TYPES, get_db_config, quote_ident


class PgVectorConfigurator(BaseConfigurator):
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
        if any(field_type == "geo" for field_type in dataset.config.schema.values()):
            raise IncompatibilityError

        id_sql = (
            "id TEXT PRIMARY KEY"
            if getattr(dataset.config, "point_id", None) == "uuid"
            else "id INTEGER PRIMARY KEY"
        )
        columns = [
            id_sql,
            f"embedding vector({dataset.config.vector_size}) NOT NULL",
        ]
        for field_name, field_type in dataset.config.schema.items():
            sql_type = PAYLOAD_SQL_TYPES.get(field_type)
            if sql_type is None:
                raise IncompatibilityError
            columns.append(f"{quote_ident(field_name)} {sql_type}")

        self.conn.execute(f"CREATE TABLE items ({', '.join(columns)});")
        self.conn.execute("ALTER TABLE items ALTER COLUMN embedding SET STORAGE PLAIN")
        for field_name in dataset.config.schema:
            self.conn.execute(
                f"CREATE INDEX ON items ({quote_ident(field_name)});"
            )

    def delete_client(self):
        if self.conn:
            self.conn.close()
            self.conn = None
