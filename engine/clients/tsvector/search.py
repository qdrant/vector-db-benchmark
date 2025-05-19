from typing import List, Tuple

import numpy as np
import psycopg
from pgvector.psycopg import register_vector

from dataset_reader.base_reader import Query
from engine.base_client.distances import Distance
from engine.base_client.search import BaseSearcher
from engine.clients.tsvector.config import get_db_config
from engine.clients.tsvector.parser import TsVectorConditionParser

CONNECTION_SETTINGS = [
    "set work_mem = '2GB';",
    "set maintenance_work_mem = '8GB';" "set max_parallel_workers_per_gather = 0;",
    "set enable_seqscan=0;",
    "set jit = 'off';",
]


class TsVectorSearcher(BaseSearcher):
    conn = None
    cur = None
    distance = None
    search_params = {}
    parser = TsVectorConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.distance = distance
        cls.conn = psycopg.connect(**get_db_config(host, connection_params))
        register_vector(cls.conn)
        cls.cur = cls.conn.cursor()

        if distance == Distance.COSINE:
            cls.query = "SELECT id, embedding <=> %s AS _score FROM items ORDER BY _score LIMIT %s"
        elif distance == Distance.L2:
            cls.query = "SELECT id, embedding <-> %s AS _score FROM items ORDER BY _score LIMIT %s"
        else:
            raise NotImplementedError(f"Unsupported distance metric {cls.distance}")

        cls.cur.execute(
            "set diskann.query_search_list_size = %d"
            % search_params["query_search_list_size"]
        )
        print(
            "set diskann.query_search_list_size = %d"
            % search_params["query_search_list_size"]
        )
        cls.cur.execute(
            "set diskann.query_rescore = %d" % search_params["query_rescore"]
        )
        print("set diskann.query_rescore = %d" % search_params["query_rescore"])

        for setting in CONNECTION_SETTINGS:
            cls.cur.execute(setting)

        print("Prewarming...")
        cls.cur.execute(
            "select format($$%I.%I$$, chunk_schema, chunk_name) from timescaledb_information.chunks k where hypertable_name = 'items'"
        )
        chunks = [row[0] for row in cls.cur]
        for chunk in chunks:
            print(f"prewarming chunk heap {chunk}")
            cls.cur.execute(f"select pg_prewarm('{chunk}'::regclass, mode=>'buffer')")
            cls.cur.fetchall()

        cls.cur.execute(
            """
                select format($$%I.%I$$, x.schemaname, x.indexname)
                from timescaledb_information.chunks k
                inner join pg_catalog.pg_indexes x on (k.chunk_schema = x.schemaname and k.chunk_name = x.tablename)
                where x.indexname ilike '%_embedding_%'
                and k.hypertable_name = 'items'"""
        )
        chunks = [row[0] for row in cls.cur]
        for chunk_index in chunks:
            print(f"prewarming chunk index {chunk_index}")
            cls.cur.execute(
                f"select pg_prewarm('{chunk_index}'::regclass, mode=>'buffer')"
            )
            cls.cur.fetchall()

    @classmethod
    def search_one(cls, query: Query, top) -> List[Tuple[int, float]]:
        # TODO: Use query.metaconditions for datasets with filtering
        cls.cur.execute(
            cls.query, (np.array(query.vector), top), binary=True, prepare=True
        )
        res = cls.cur.fetchall()
        return [(hit[0], float(hit[1])) for hit in res]

    @classmethod
    def delete_client(cls):
        if cls.cur:
            cls.cur.close()
            cls.conn.close()
