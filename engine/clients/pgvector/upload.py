from io import BytesIO
from typing import List, Optional

import psycopg2
from pgvector.psycopg2 import register_vector

from engine.base_client.upload import BaseUploader
from engine.clients.pgvector.config import get_db_config


class PgVectorUploader(BaseUploader):
    conn = None
    cur = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.conn = psycopg2.connect(**get_db_config(host, connection_params))
        register_vector(cls.conn)
        cls.cur = cls.conn.cursor()
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(
        cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]
    ):
        # COPY is faster than INSERT:
        data = BytesIO()
        for i, embedding in zip(ids, vectors):
            data.write(f"{i}\t{embedding}\n".encode("utf-8"))

        data.seek(0)
        cls.cur.copy_from(data, "items", columns=("id", "embedding"))
        cls.conn.commit()

    @classmethod
    def delete_client(cls):
        cls.cur.close()
        cls.conn.close()
