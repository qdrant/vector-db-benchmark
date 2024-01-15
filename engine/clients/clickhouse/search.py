import multiprocessing as mp
import uuid
from typing import List, Tuple

import clickhouse_connect
from clickhouse_connect.driver import Client

from engine.base_client.search import BaseSearcher
from engine.clients.clickhouse.config import (
    CLICKHOUSE_TABLE,
    CLICKHOUSE_PASSWORD,
    CLICKHOUSE_PORT,
    CLICKHOUSE_USER, DISTANCE_MAPPING, CLICKHOUSE_DATABASE,
)
from engine.clients.clickhouse.parser import ClickHouseConditionParser


class ClosableClickHouse(Client):
    def __del__(self):
        self.close()


class ClickHouseSearcher(BaseSearcher):
    search_params = {}
    client: Client = None
    parser = ClickHouseConditionParser()
    distance: str = None

    @classmethod
    def get_mp_start_method(cls):
        return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.client: Client = clickhouse_connect.get_client(host=host, username=CLICKHOUSE_USER,
                                                           password=CLICKHOUSE_PASSWORD, database=CLICKHOUSE_DATABASE,
                                                           port=CLICKHOUSE_PORT, **connection_params)
        cls.search_params = search_params
        cls.distance = DISTANCE_MAPPING[distance]
        cls.use_projections = search_params["use_projections"] if "use_projections" in search_params else False
        if "use_projections" in search_params:
            del search_params["use_projections"]

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        where_condition = cls.parser.parse(meta_conditions)
        if where_condition is None:
            where_condition = "1=1"
        if cls.use_projections:
            statement = f"""
                WITH 128 AS num_bits, ( SELECT groupArray(projection) AS projections FROM (SELECT * FROM {CLICKHOUSE_TABLE}_planes LIMIT num_bits)) AS projections,
                    (SELECT arraySum((projection, bit) -> bitShiftLeft(toUInt128(dotProduct({vector}, projection) > 0), bit), projections, range(num_bits))) AS target
                SELECT id, {cls.distance}(vector, {vector}) as score FROM {CLICKHOUSE_TABLE}_lsh PREWHERE bitHammingDistance(bits, target) <= 30 WHERE {where_condition} ORDER BY score ASC LIMIT {top}
            """
        else:
            statement = (f"SELECT id, {cls.distance}(vector, {vector}) as score FROM {CLICKHOUSE_TABLE} "
                         f"WHERE {where_condition} ORDER BY score ASC LIMIT {top}")
        response = cls.client.query(statement, settings=cls.search_params)
        return [
            (row[0], row[1])
            for row in response.result_rows
        ]
