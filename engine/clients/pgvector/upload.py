from typing import List, Optional

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.pgvector.config import get_db_config


class PgVectorUploader(BaseUploader):
    conn = None
    cur = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.conn = psycopg.connect(**get_db_config(host, connection_params))
        register_vector(cls.conn)
        cls.cur = cls.conn.cursor()
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        vectors = np.array(vectors)

        # Copy is faster than insert
        with cls.cur.copy("COPY items (id, embedding) FROM STDIN") as copy:
            for record in batch:
                copy.write_row((record.id, record.vector))

    @classmethod
    def delete_client(cls):
        if cls.cur:
            cls.cur.close()
            cls.conn.close()
