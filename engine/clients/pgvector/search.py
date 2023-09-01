import multiprocessing as mp
from typing import List, Tuple
import numpy as np

import psycopg2
from pgvector.psycopg2 import register_vector

from engine.base_client.search import BaseSearcher
from engine.clients.pgvector.config import PGVECTOR_TABLE_NAME, DISTANCE_QUERY_MAPPING, get_pgvector_connection_string, DISTANCE_MAPPING, DISTANCE_QUERY_MAPPING_END
from engine.clients.pgvector.parser import PGVectorConditionParser


class PGVectorSearcher(BaseSearcher):
    search_params = {}
    client = None
    parser = PGVectorConditionParser()
    distance = None

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.client = psycopg2.connect(get_pgvector_connection_string(host))
        register_vector(cls.client)
        cls.distance = distance
        cls.search_params = search_params
        #cls.set_probes()
    
    @classmethod
    def set_probes(cls):
        num_probes = cls.search_params.get("num_probes", 33)
        with cls.client.cursor() as cur:
            print(f"SET ivfflat.probes = {num_probes};")
            cur.execute(f"SET ivfflat.probes = {num_probes};")
            cls.client.commit()

    @classmethod
    def get_mp_start_method(cls):
        return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        #print(vector)
        np_vector = np.array(vector)
        #print(np_vector)
        meta_conditions = cls.parser.parse(meta_conditions)
        distance_calculation = DISTANCE_QUERY_MAPPING.get(cls.distance)
        distance_metric = DISTANCE_MAPPING.get(cls.distance)
        distance_calculation_end = DISTANCE_QUERY_MAPPING_END.get(cls.distance)
        
        search_query = """
                    SELECT id, {} %s{} AS score 
                    FROM (
                        SELECT id, embedding 
                        FROM {} 
                        ORDER BY embedding {} %s LIMIT {}
                    ) AS e
                    """.format(distance_calculation, distance_calculation_end, PGVECTOR_TABLE_NAME, distance_metric, top)
        
        search_query += meta_conditions if meta_conditions else ''
        search_query += f"ORDER BY score LIMIT {top}"
        search_query += f";"
        with cls.client.cursor() as cur:
            cur.execute(search_query, (np_vector, np_vector))
            res = cur.fetchall()
            return [(row[0], row[1]) for row in res]