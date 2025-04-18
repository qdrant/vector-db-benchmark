import clickhouse_connect

from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.clickhouse.config import get_db_config


class CHVectorConfigurator(BaseConfigurator):
    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self.client = clickhouse_connect.driver.create_client(
            **get_db_config(connection_params)
        )
        print("configure connection created")

    def clean(self):
        self.client.command(
            cmd="DROP TABLE IF EXISTS items;",
        )

    def recreate(self, dataset: Dataset, collection_params):
        if dataset.config.distance == Distance.DOT:
            raise IncompatibilityError

        self.client.command(
            cmd="""CREATE TABLE items (
                id UInt64,
                embedding Array(Float64)
                )
                ENGINE = MergeTree()
                ORDER BY id
                ;"""
        )
        self.client.close()

    def delete_client(self):
        self.client.close()
