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
    score_sql = None

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.conn = psycopg.connect(**get_db_config(host, connection_params))
        register_vector(cls.conn)
        cls.cur = cls.conn.cursor()
        cls.cur.execute(f"SET hnsw.ef_search = {search_params['config']['hnsw_ef']}")
        if distance == Distance.COSINE:
            cls.score_sql = "embedding <=> %s"
        elif distance == Distance.L2:
            cls.score_sql = "embedding <-> %s"
        else:
            raise NotImplementedError(f"Unsupported distance metric {distance}")

    @classmethod
    def search_one(cls, query: Query, top) -> List[Tuple[int, float]]:
        condition = cls.parser.parse(query.meta_conditions)
        params = [np.array(query.vector)]
        where_sql = ""
        if condition:
            where_sql, where_params = condition
            where_sql = f" WHERE {where_sql}"
            params.extend(where_params)
        params.append(top)
        cls.cur.execute(
            f"SELECT id, {cls.score_sql} AS _score FROM items{where_sql} ORDER BY _score LIMIT %s",
            params,
            binary=True,
            prepare=True,
        )
        return [(int(row_id), score) for row_id, score in cls.cur.fetchall()]

    @classmethod
    def delete_client(cls):
        if cls.cur:
            cls.cur.close()
            cls.conn.close()
