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

    def search_all(self, collection_name, filename, ef, parallel):
        latencies = self.searcher.search_all(
            self.url, collection_name, filename, ef, parallel
        )
        print(f"search::latency = {sum(latencies) / parallel}")
        return latencies

    def upload(self, collection_name, filename, batch_size, parallel):
        latencies = self.uploader.upload(
            self.url, collection_name, filename, batch_size, parallel
        )
        print("latencies are: ", latencies)
        print("parallel is: ", parallel)
        print(f"upload::latency = {sum(latencies) / parallel}")
        return latencies

    def configure(
        self, collection_name, ef_construction, max_connections, distance, vector_size
    ):
        latency = self.configurator.configure(
            collection_name, ef_construction, max_connections, distance, vector_size
        )
        print(f"configure::latency = {latency}")
        return latency
