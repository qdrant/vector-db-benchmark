from typing import List, Tuple

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from dataset_reader.base_reader import Query
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
        cls.cur.execute(f"SET hnsw.ef_search = {search_params['config']['hnsw_ef']}")
        if distance == Distance.COSINE:
            cls.query_template = "SELECT id, embedding <=> %(vector)s AS _score FROM items{where} ORDER BY _score LIMIT %(top)s"
        elif distance == Distance.L2:
            cls.query_template = "SELECT id, embedding <-> %(vector)s AS _score FROM items{where} ORDER BY _score LIMIT %(top)s"
        else:
            raise NotImplementedError(f"Unsupported distance metric {cls.distance}")

    @classmethod
    def search_one(cls, query: Query, top) -> List[Tuple[int, float]]:
        params = {"vector": np.array(query.vector), "top": top}
        condition = cls.parser.parse(query.meta_conditions)
        where = ""
        if condition is not None:
            clause, filter_params = condition
            if clause:
                where = f" WHERE {clause}"
                params.update(filter_params)

        cls.cur.execute(
            cls.query_template.format(where=where), params, binary=True, prepare=True
        )
        return cls.cur.fetchall()

    @classmethod
    def delete_client(cls):
        if cls.cur:
            cls.cur.close()
            cls.conn.close()
