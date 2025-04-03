from typing import List, Tuple
import clickhouse_connect

import numpy as np
from clickhouse_connect.driver.query import QueryResult
66
from dataset_reader.base_reader import Query
from engine.base_client.distances import Distance
from engine.base_client.search import BaseSearcher
from engine.clients.clickhouse.config import get_db_config
from engine.clients.clickhouse.parser import CHVectorConditionParser


class CHVectorSearcher(BaseSearcher):
    distance = None
    search_params = {}
    parser = CHVectorConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.client = clickhouse_connect.driver.create_client(**get_db_config(connection_params))
        if distance == Distance.COSINE:
            cls.query: str = "SELECT id, cosineDistance(embedding, {vector:Array(Float64)}) AS _score FROM items ORDER BY _score LIMIT {top:UInt8} OFFSET 1"
        elif distance == Distance.L2:
            cls.query: str = "SELECT id, L2Distance(embedding, {vector:Array(Float64)}) AS _score FROM items ORDER BY _score LIMIT {top:UInt8} OFFSET 1"
        else:
            raise NotImplementedError(f"Unsupported distance metric {cls.distance}")

    @classmethod
    def search_one(cls, query: Query, top) -> List[Tuple[int, float]]:
        # TODO: Use query.metaconditions for datasets with filtering
        query_summary: QueryResult = cls.client.query(
            cls.query, parameters={'vector': query.vector, 'top':top}
        )
        #print(type(query_summary.result_rows))
        #print(type(query_summary.result_rows[0]))
        #print(type(query_summary.result_rows[0][0]))
        return query_summary.result_rows

    @classmethod
    def delete_client(cls):
        cls.client.close()
