from typing import Iterable

from dataset_reader.base_reader import Query
from engine.base_client.configure import BaseConfigurator
from engine.base_client.search import BaseSearcher
from engine.base_client.upload import BaseUploader


class BaseClient:
    def __init__(
        self,
        url,
        configurator: BaseConfigurator,
        uploader: BaseUploader,
        searcher: BaseSearcher,
    ):
        self.url = url
        self.configurator = configurator
        self.uploader = uploader
        self.searcher = searcher

    def search_all(
        self, connection_params, search_params, queries: Iterable[Query], parallel,
    ):
        precisions, latencies = self.searcher.search_all(
            self.url, connection_params, search_params, queries, parallel,
        )
        print(f"search::latency = {sum(latencies) / parallel}")
        print(f"search::precisions = {sum(precisions) / len(precisions)}")
        return latencies

    def upload(self, filename, batch_size, parallel, connection_params):
        latencies = self.uploader.upload(
            self.url, filename, batch_size, parallel, connection_params
        )
        print(f"upload::latency = {sum(latencies) / parallel}")
        return latencies

    def configure(self, distance, vector_size, collection_params):
        latency = self.configurator.configure(distance, vector_size, collection_params)
        print(f"configure::latency = {latency}")
        return latency
