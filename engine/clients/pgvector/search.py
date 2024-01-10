import multiprocessing as mp
from typing import List, Tuple

import numpy as np
from pgvector.psycopg import register_vector
import psycopg

from engine.base_client.distances import Distance
from engine.base_client.search import BaseSearcher
from engine.clients.pgvector.config import get_db_config
from engine.clients.pgvector.parser import PgVectorConditionParser


class PgVectorSearcher(BaseSearcher):
    conn = None
    cur = None
    distance = None
    search_params = {}
    parser = PgVectorConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.conn = psycopg.connect(**get_db_config(host, connection_params))
        register_vector(cls.conn)
        cls.cur = cls.conn.cursor()
        cls.distance = distance
        cls.search_params = search_params["search_params"]

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        cls.cur.execute(f"SET hnsw.ef_search = {cls.search_params['hnsw_ef']}")

        if cls.distance == Distance.COSINE:
            query = f"SELECT id, embedding <=> %s AS _score FROM items ORDER BY _score LIMIT {top};"
        elif cls.distance == Distance.L2:
            query = f"SELECT id, embedding <-> %s AS _score FROM items ORDER BY _score LIMIT {top};"
        else:
            raise NotImplementedError(f"Unsupported distance metric {cls.distance}")

        cls.cur.execute(
            query,
            (np.array(vector),),
        )
        return cls.cur.fetchall()

    @classmethod
    def close(cls):
        if cls.cur:
            cls.cur.close()
            cls.conn.close()
