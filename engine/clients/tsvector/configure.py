import pgvector.psycopg
import psycopg

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.clients.pgvector.config import get_db_config


class TsVectorConfigurator(BaseConfigurator):
    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self.conn = psycopg.connect(**get_db_config(host, connection_params))
        print("configure connection created")
        self.conn.execute("create extension if not exists timescaledb")
        self.conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        self.conn.execute("create extension if not exists vectorscale cascade")
        pgvector.psycopg.register_vector(self.conn)

    def clean(self):
        print("Make sure we don't remove the table")

    def recreate(self, dataset: Dataset, collection_params):
        print("Make sure we don't remove the table")

    def delete_client(self):
        self.conn.close()
