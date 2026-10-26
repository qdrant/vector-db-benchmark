from typing import List

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from dataset_reader.base_reader import Record
from engine.base_client import IncompatibilityError
from engine.base_client.distances import Distance
from engine.base_client.upload import BaseUploader
from engine.clients.pgvector.config import COPY_TYPE_NAMES, get_db_config, quote_ident


class PgVectorUploader(BaseUploader):
    DISTANCE_MAPPING = {
        Distance.L2: "vector_l2_ops",
        Distance.COSINE: "vector_cosine_ops",
    }
    conn = None
    cur = None
    upload_params = {}
    payload_columns = []
    id_copy_type = "integer"

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.conn = psycopg.connect(**get_db_config(host, connection_params))
        register_vector(cls.conn)
        cls.cur = cls.conn.cursor()
        cls.upload_params = upload_params
        cls.payload_columns = list(
            cls.cur.execute(
                """
                SELECT column_name, udt_name
                FROM information_schema.columns
                WHERE table_name = 'items'
                  AND column_name NOT IN ('id', 'embedding')
                ORDER BY ordinal_position
                """
            )
        )
        id_udt = cls.cur.execute(
            """
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_name = 'items' AND column_name = 'id'
            """
        ).fetchone()
        cls.id_copy_type = "text" if id_udt and id_udt[0] == "text" else "integer"

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        ids, vectors, payload_rows = [], [], []
        for record in batch:
            ids.append(
                str(record.id) if cls.id_copy_type == "text" else record.id
            )
            vectors.append(record.vector)
            meta = record.metadata or {}
            values = []
            for column_name, _udt_name in cls.payload_columns:
                value = meta.get(column_name)
                if isinstance(value, list):
                    value = ";".join(str(item) for item in value)
                values.append(value)
            payload_rows.append(values)

        vectors = np.array(vectors)
        column_sql = ", ".join(
            ["id", "embedding"]
            + [quote_ident(name) for name, _ in cls.payload_columns]
        )
        copy_types = [cls.id_copy_type, "vector"] + [
            COPY_TYPE_NAMES.get(udt_name, "text")
            for _name, udt_name in cls.payload_columns
        ]
        with cls.cur.copy(
            f"COPY items ({column_sql}) FROM STDIN WITH (FORMAT BINARY)"
        ) as copy:
            copy.set_types(copy_types)
            for i, embedding, payload in zip(ids, vectors, payload_rows):
                copy.write_row((i, embedding, *payload))

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
