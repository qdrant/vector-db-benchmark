import math
from typing import List, Optional

import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2.extras import execute_values

from engine.base_client.upload import BaseUploader
from engine.clients.pgvector.config import (
    DISTANCE_INDEX_MAPPING,
    PGVECTOR_TABLE_NAME,
    get_pgvector_connection_string,
)


class PGVectorUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.client = psycopg2.connect(get_pgvector_connection_string(host))
        register_vector(cls.client)
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(
        cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]
    ):

        embeddings = list(zip(ids, vectors))
        upload_batch_string = "INSERT INTO {} (id, embedding) VALUES %s".format(
            PGVECTOR_TABLE_NAME
        )
        with cls.client.cursor() as cur:
            execute_values(cur, upload_batch_string, embeddings)
        cls.client.commit()

    @classmethod
    def post_upload(cls, distance):
        index_type = DISTANCE_INDEX_MAPPING.get(distance)

        with cls.client.cursor() as cur:
            if not cls.upload_params.get("num_lists"):
                cur.execute(f"SELECT count(*) as cnt FROM {PGVECTOR_TABLE_NAME};")
                num_records = cur.fetchone()[0]
                num_lists = num_records / 1000
                if num_lists < 10:
                    num_lists = 10
                if num_records > 1000000:
                    num_lists = math.sqrt(num_records)
            else:
                num_lists = cls.upload_params.get("num_lists")
            print(
                f"""CREATE INDEX ON {PGVECTOR_TABLE_NAME}
                        USING ivfflat (embedding {index_type})
                        WITH (lists={num_lists});"""
            )
            cur.execute(
                f"""CREATE INDEX ON {PGVECTOR_TABLE_NAME}
                        USING ivfflat (embedding {index_type})
                        WITH (lists={num_lists});"""
            )

        cls.client.commit()

        return {}
