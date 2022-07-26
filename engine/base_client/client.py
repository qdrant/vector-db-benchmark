class BaseClient:
    def __init__(self, url, configurator, uploader, searcher):
        self.url = url
        self.configurator = configurator(self.url)
        self.uploader = uploader
        self.searcher = searcher

    def search_all(self, collection_name, filename, parallel):
        latencies = self.searcher.search_all(
            self.url, collection_name, filename, parallel
        )
        print(f"search::latency = {sum(latencies) / parallel}")
        return latencies

    def upload(self, collection_name, filename, batch_size, parallel):
        latencies = self.uploader.upload(
            self.url, collection_name, filename, batch_size, parallel
        )
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
