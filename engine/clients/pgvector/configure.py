import psycopg2
from pgvector.psycopg2 import register_vector

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.pgvector.config import PGVECTOR_TABLE_NAME, FIELD_MAPPING, get_pgvector_connection_string


class PGVectorConfigurator(BaseConfigurator):

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        print("connection_params: ", connection_params, flush=True)
        self.client = psycopg2.connect(get_pgvector_connection_string(host))
        register_vector(self.client)

    def clean(self):
        with self.client.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {PGVECTOR_TABLE_NAME}")

    def recreate(self, dataset: Dataset, collection_params):
        fields = []
        for field_name, field_type in dataset.config.schema.items():
            fields.append(f'{field_name} {FIELD_MAPPING.get(field_type)}')

        with self.client.cursor() as cur:
            create_table_string = f""" CREATE TABLE IF NOT EXISTS {PGVECTOR_TABLE_NAME} (
                                        id serial PRIMARY KEY, 
                                        embedding VECTOR({dataset.config.vector_size})"""
            #create_table_string += ", ".join(fields)
            create_table_string += ")"
            cur.execute(create_table_string)
            cur.execute(f"""SELECT count(*) FROM {PGVECTOR_TABLE_NAME}""")

        self.client.commit()
            