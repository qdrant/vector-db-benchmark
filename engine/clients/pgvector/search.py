import multiprocessing as mp
from typing import List, Tuple

import psycopg
from pgvector.psycopg import register_vector

from engine.base_client.search import BaseSearcher
from engine.clients.pgvector.config import PGVECTOR_COLLECTION_NAME
from engine.clients.pgvector.parser import PgvectorConditionParser


class PgvectorSearcher(BaseSearcher):
    search_params = {}
    client: QdrantClient = None
    parser = PgvectorConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.client = psycopg.connect(host, **connection_params)
        register_vector(cls.client)
        cls.search_params = search_params

    @classmethod
    def get_mp_start_method(cls):
        return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        
        vector = "[" + ", ".join(str(x) for x in vector) + "]"
        meta_conditions = cls.parser.parse(meta_conditions)

        query = f"""
              SELECT
                *,
                ("vector" <=> '{vector}') * -1 AS similarity
              FROM
                {PGVECTOR_COLLECTION_NAME}
          """
        query += meta_conditions
        query += f"ORDER BY similarity LIMIT {top};"

        with cls.client.cursor() as cur:
            cur.execute(query)
            res = cur.fetchall()
            return [(row["id"], row["similarity"]) for row in res]