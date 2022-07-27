from abc import ABC

from engine.base_client.client import BaseClient
from engine.base_client.configure import BaseConfigurator
from engine.base_client.search import BaseSearcher
from engine.base_client.upload import BaseUploader
from engine.clients.qdrant.configure import QdrantConfigurator
from engine.clients.qdrant.search import QdrantSearcher
from engine.clients.qdrant.upload import QdrantUploader


ENGINE_CONFIGURATORS = {
    "qdrant": QdrantConfigurator,
}

ENGINE_UPLOADERS = {
    "qdrant": QdrantUploader,
}

ENGINE_SEARCHERS = {
    "qdrant": QdrantSearcher,
}


class ClientFactory(ABC):
    def __init__(self, host):
        self.host = host

    def _create_configurator(self, experiment) -> BaseConfigurator:
        engine_configurator_class = ENGINE_CONFIGURATORS[experiment["engine"]]
        engine_configurator = engine_configurator_class(
            self.host,
            experiment.get("collection_params", {}),
            experiment.get("connection_params", {}),
        )
        return engine_configurator

    def _create_uploader(self, experiment) -> BaseUploader:
        engine_uploader_class = ENGINE_UPLOADERS[experiment["engine"]]
        engine_uploader = engine_uploader_class(
            self.host,
            experiment.get("connection_params", {}),
            experiment.get("upload_params", {}),
        )
        return engine_uploader

    def _create_searcher(self, experiment) -> BaseSearcher:
        engine_searcher_class = ENGINE_SEARCHERS[experiment["engine"]]
        engine_searcher = engine_searcher_class(
            self.host,
            experiment.get("connection_params", {}),
            experiment.get("search_params", {}),
        )
        return engine_searcher

    def build_client(self, experiment):
        return BaseClient(
            name=experiment["name"],
            configurator=self._create_configurator(experiment),
            uploader=self._create_uploader(experiment),
            searcher=self._create_searcher(experiment),
        )
