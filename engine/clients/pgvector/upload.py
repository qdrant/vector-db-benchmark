from typing import List

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from dataset_reader.base_reader import Record
from engine.base_client import IncompatibilityError
from engine.base_client.distances import Distance
from engine.base_client.upload import BaseUploader
from engine.clients.pgvector.config import get_db_config


class PgVectorUploader(BaseUploader):
    DISTANCE_MAPPING = {
        Distance.L2: "vector_l2_ops",
        Distance.COSINE: "vector_cosine_ops",
    }
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
        ids, vectors = [], []
        for record in batch:
            ids.append(record.id)
            vectors.append(record.vector)

        vectors = np.array(vectors)
        # Copy is faster than insert
        with cls.cur.copy(
            "COPY items (id, embedding) FROM STDIN WITH (FORMAT BINARY)"
        ) as copy:
            copy.set_types(["integer", "vector"])
            for i, embedding in zip(ids, vectors):
                copy.write_row((i, embedding))

    @classmethod
    def post_upload(cls, distance):
        try:
            hnsw_distance_type = cls.DISTANCE_MAPPING[distance]
        except KeyError:
            raise IncompatibilityError(f"Unsupported distance metric: {distance}")

        cls.conn.execute("SET max_parallel_workers = 128")
        cls.conn.execute("SET max_parallel_maintenance_workers = 128")
        cls.conn.execute(
            f"CREATE INDEX ON items USING hnsw (embedding {hnsw_distance_type}) WITH (m = {cls.upload_params['hnsw_config']['m']}, ef_construction = {cls.upload_params['hnsw_config']['ef_construct']})"
        )

        return {}

    @classmethod
    def delete_client(cls):
        if cls.cur:
            cls.cur.close()
            cls.conn.close()
