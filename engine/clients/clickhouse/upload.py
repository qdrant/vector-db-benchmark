import multiprocessing as mp
import uuid
from typing import List, Optional

import clickhouse_connect
from clickhouse_connect.driver import Client
from clickhouse_connect.driver.models import ColumnDef

from engine.base_client.upload import BaseUploader
from engine.clients.clickhouse.config import (
    CLICKHOUSE_TABLE,
    CLICKHOUSE_PASSWORD,
    CLICKHOUSE_PORT,
    CLICKHOUSE_USER,
    CLICKHOUSE_DATABASE
)


class ClosableClickHouse(Client):
    def __del__(self):
        self.close()


class ClickHouseUploader(BaseUploader):
    client: Client = None
    upload_params = {}
    column_names = []
    column_types = []
    @classmethod
    def get_mp_start_method(cls):
        return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.client: Client = clickhouse_connect.get_client(host=host, username=CLICKHOUSE_USER,
                                                           password=CLICKHOUSE_PASSWORD, database=CLICKHOUSE_DATABASE,
                                                           port=CLICKHOUSE_PORT,
                                                           **connection_params)
        cls.upload_params = upload_params
        describe_result = cls.client.query(f'DESCRIBE TABLE {CLICKHOUSE_TABLE}')
        column_defs = [ColumnDef(**row) for row in describe_result.named_results()
                       if row['default_type'] not in ('ALIAS', 'MATERIALIZED')]
        cls.column_names = [cd.name for cd in column_defs]
        cls.column_types = [cd.ch_type for cd in column_defs]
        cls.use_simple_projections = upload_params[
            "use_simple_projections"] if "use_simple_projections" in upload_params else False
        cls.use_projections = upload_params[
            "use_projections"] if "use_projections" in upload_params else False
        cls.vector_length = 0

    @classmethod
    def upload_batch(
            cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]
    ):
        data = []
        if metadata is None:
            metadata = [{}] * len(vectors)
        # we assume all rows have all columns
        for idx, vector, payload in zip(ids, vectors, metadata):
            if idx == 0:
                cls.vector_length = len(vector)
            row = [idx, vector]
            if payload:
                for column_name in cls.column_names:
                    row.append(payload[column_name])
            data.append(row)
        cls.client.insert(CLICKHOUSE_TABLE, data=data, column_names=cls.column_names, column_types=cls.column_types)

    @classmethod
    def post_upload(cls, _distance):
        response = cls.client.query(f"SELECT engine FROM system.tables WHERE name='{CLICKHOUSE_TABLE}' AND database='{CLICKHOUSE_DATABASE}'")
        if response.first_row[0] != 'Memory':
            cls.client.command(f"OPTIMIZE TABLE {CLICKHOUSE_TABLE} FINAL", settings={"alter_sync": 2})
        response = cls.client.query(
            f"SELECT count() FROM system.tables WHERE name='{CLICKHOUSE_TABLE}_lsh' OR name='{CLICKHOUSE_TABLE}_planes' "
            f"AND database='{CLICKHOUSE_DATABASE}'")
        if response.first_row[0] == 2 and (cls.use_simple_projections or cls.use_projections):
            # we have projection tables, populate them
            if cls.use_simple_projections:
                cls.client.command(
                    f"INSERT INTO {CLICKHOUSE_TABLE}_planes SELECT projection / L2Norm(projection) AS projection FROM "
                    f"( SELECT arrayJoin(arraySplit((x, y) -> y, groupArray(e), arrayMap(x -> ((x % {cls.vector_length}) = 0)"
                    f", range(128 * {cls.vector_length})))) AS projection FROM ( SELECT CAST(randNormal(0, 1), 'Float32') AS e "
                    f"FROM numbers(128 * {cls.vector_length})))")
                cls.client.command(f"""INSERT INTO {CLICKHOUSE_TABLE}_lsh WITH 128 AS num_bits,
                        ( SELECT groupArray(projection) AS projections FROM
                            ( SELECT * FROM {CLICKHOUSE_TABLE}_planes LIMIT num_bits )
                        ) AS projections
                    SELECT *, arraySum((projection, bit) -> bitShiftLeft(toUInt128(dotProduct(vector, projection) > 0), bit), projections, range(num_bits)) AS bits
                    FROM {CLICKHOUSE_TABLE} SETTINGS max_block_size = 1000""")
            elif cls.use_projections:
                cls.client.command(f"INSERT INTO {CLICKHOUSE_TABLE}_planes "
                                   f"SELECT v1 - v2 AS normal, (v1 + v2) / 2 AS offset FROM "
                                   f"(SELECT min(vector) AS v1, max(vector) AS v2 FROM "
                                   f"(SELECT vector FROM {CLICKHOUSE_TABLE} ORDER BY rand() ASC LIMIT 256) "
                                   f"GROUP BY intDiv(rowNumberInAllBlocks(), 2))")
                cls.client.command(f"""INSERT INTO {CLICKHOUSE_TABLE}_lsh
                                    WITH 128 AS num_bits,
                                       (
                                           SELECT
                                               groupArray(normal) AS normals,
                                               groupArray(offset) AS offsets
                                           FROM
                                           (
                                               SELECT *
                                               FROM {CLICKHOUSE_TABLE}_planes
                                               LIMIT num_bits
                                           )
                                       ) AS partition,
                                       partition.1 AS normals,
                                       partition.2 AS offsets
                                    SELECT
                                       *,
                                       arraySum((normal, offset, bit) -> bitShiftLeft(toUInt128(dotProduct(vector - offset, normal) > 0), bit), normals, offsets, range(num_bits)) AS bits
                                    FROM {CLICKHOUSE_TABLE}""", settings={"max_block_size": 1000})
        return {}
