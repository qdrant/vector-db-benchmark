import multiprocessing as mp
from typing import List, Tuple

import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from psycopg2.extras import RealDictCursor

from engine.base_client.search import BaseSearcher
from engine.clients.pgvector.config import get_db_config
from engine.clients.pgvector.parser import PgVectorConditionParser


class PgVectorSearcher(BaseSearcher):
    search_params = {}
    cursor = None
    parser = PgVectorConditionParser()

    @classmethod
    def get_mp_start_method(cls):
        return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.conn = psycopg2.connect(**get_db_config())
        register_vector(cls.conn)
        cls.cur = cls.conn.cursor(cursor_factory=RealDictCursor)
        cls.distance = distance
        cls.search_params = search_params

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        if cls.distance == "cosine":
            QUERY = f"SELECT id, embedding <=> %s AS _score FROM items ORDER BY _score LIMIT {top};"
        elif cls.distance == "euclidean":
            QUERY = f"SELECT id, embedding <-> %s AS _score FROM items ORDER BY _score LIMIT {top};"
        else:
            raise NotImplementedError("Unsupported distance metric")

        cls.cur.execute(
            QUERY,
            (np.array(vector),),
        )
        res = cls.cur.fetchall()

        return [(r["id"], r["_score"]) for r in res]
