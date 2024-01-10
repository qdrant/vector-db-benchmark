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
                                                           port=CLICKHOUSE_PORT, **connection_params)
        cls.upload_params = upload_params
        describe_result = cls.client.query(f'DESCRIBE TABLE {CLICKHOUSE_TABLE}')
        column_defs = [ColumnDef(**row) for row in describe_result.named_results()
                       if row['default_type'] not in ('ALIAS', 'MATERIALIZED')]
        cls.column_names = [cd.name for cd in column_defs]
        cls.column_types = [cd.ch_type for cd in column_defs]

    @classmethod
    def upload_batch(
            cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]
    ):
        data = []
        if metadata is None:
            metadata = [{}] * len(vectors)
        # we make two assumptions 1. first row contains all columns 2. all rows have all columns
        for idx, vector, payload in zip(ids, vectors, metadata):
            row = [idx, vector]
            if payload:
                for column_name in cls.column_names:
                    row.append(payload[column_name])
            data.append(row)
        cls.client.insert(CLICKHOUSE_TABLE, data=data, column_names=cls.column_names, column_types=cls.column_types)

    @classmethod
    def post_upload(cls, _distance):
        cls.client.command(f"OPTIMIZE TABLE {CLICKHOUSE_TABLE} FINAL", settings={"alter_sync": 2})
        return {}
