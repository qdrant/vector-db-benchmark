from typing import Optional

import mysql.connector
from doris_vector_search import AuthOptions, DorisVectorClient
from mysql.connector import ProgrammingError

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.doris.config import (
    DEFAULT_DORIS_DATABASE,
    DEFAULT_DORIS_TABLE,
    DISTANCE_MAPPING,
)


class DorisConfigurator(BaseConfigurator):
    SPARSE_VECTOR_SUPPORT = False

    DISTANCE_MAPPING = {
        Distance.L2: DISTANCE_MAPPING["l2"],
        Distance.DOT: DISTANCE_MAPPING["dot"],
        Distance.COSINE: DISTANCE_MAPPING["cosine"],
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)

        database = collection_params.get("database", DEFAULT_DORIS_DATABASE)
        auth = AuthOptions(
            host=connection_params.get("host", host),
            query_port=connection_params.get("query_port", 9030),
            http_port=connection_params.get("http_port", 8030),
            user=connection_params.get("user", "root"),
            password=connection_params.get("password", ""),
        )
        # Ensure database exists before creating main client
        try:
            tmp_conn = mysql.connector.connect(
                host=auth.host,
                port=auth.query_port,
                user=auth.user,
                password=auth.password,
            )
            cursor = tmp_conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
            cursor.close()
            tmp_conn.close()
        except ProgrammingError:
            # If we cannot create database, proceed and let actual client raise clearer error
            pass
        self.client = DorisVectorClient(database=database, auth_options=auth)

    def clean(self):
        table_name = self.collection_params.get("table_name", DEFAULT_DORIS_TABLE)
        try:
            self.client.drop_table(table_name)
        except Exception:
            # Table may not exist, ignore
            pass

    def recreate(self, dataset: Dataset, collection_params) -> Optional[dict]:
        # Doris table and index are created lazily on first upload batch to infer schema
        # Return execution params which depend on distance/metric mapping
        return {}

    def execution_params(self, distance, vector_size) -> dict:
        metric = self.DISTANCE_MAPPING.get(distance)
        # Provide search-related session variables tuning if needed
        return {"metric_type": metric}

    def delete_client(self):
        try:
            self.client.close()
        except Exception:
            pass
