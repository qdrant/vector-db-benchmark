from abc import ABC
from typing import List, Type

from engine.base_client.client import (
    BaseClient,
    BaseConfigurator,
    BaseSearcher,
    BaseUploader,
)

# Maps engine name to (module_path, configurator, uploader, searcher) class names.
# Imports are deferred so missing/broken engine dependencies don't block other engines.
_ENGINE_MODULES = {
    "turbopuffer": (
        "engine.clients.turbopuffer",
        "TurbopufferConfigurator",
        "TurbopufferUploader",
        "TurbopufferSearcher",
    ),
    "qdrant": (
        "engine.clients.qdrant",
        "QdrantConfigurator",
        "QdrantUploader",
        "QdrantSearcher",
    ),
    "qdrant_native": (
        "engine.clients.qdrant_native",
        "QdrantNativeConfigurator",
        "QdrantNativeUploader",
        "QdrantNativeSearcher",
    ),
    "qdrant_hybrid": (
        "engine.clients.qdrant_hybrid",
        "QdrantHybridConfigurator",
        "QdrantHybridUploader",
        "QdrantHybridSearcher",
    ),
    "weaviate": (
        "engine.clients.weaviate",
        "WeaviateConfigurator",
        "WeaviateUploader",
        "WeaviateSearcher",
    ),
    "milvus": (
        "engine.clients.milvus",
        "MilvusConfigurator",
        "MilvusUploader",
        "MilvusSearcher",
    ),
    "elasticsearch": (
        "engine.clients.elasticsearch",
        "ElasticConfigurator",
        "ElasticUploader",
        "ElasticSearcher",
    ),
    "opensearch": (
        "engine.clients.opensearch",
        "OpenSearchConfigurator",
        "OpenSearchUploader",
        "OpenSearchSearcher",
    ),
    "redis": (
        "engine.clients.redis",
        "RedisConfigurator",
        "RedisUploader",
        "RedisSearcher",
    ),
    "pgvector": (
        "engine.clients.pgvector",
        "PgVectorConfigurator",
        "PgVectorUploader",
        "PgVectorSearcher",
    ),
}


def _load_engine(engine: str):
    if engine not in _ENGINE_MODULES:
        raise ValueError(f"Unknown engine: {engine!r}. Available: {list(_ENGINE_MODULES)}")
    import importlib
    module_path, configurator_cls, uploader_cls, searcher_cls = _ENGINE_MODULES[engine]
    module = importlib.import_module(module_path)
    return (
        getattr(module, configurator_cls),
        getattr(module, uploader_cls),
        getattr(module, searcher_cls),
    )


class ClientFactory(ABC):
    def __init__(self, host):
        self.host = host
        self.engine = None

    def _create_configurator(self, experiment) -> BaseConfigurator:
        self.engine = experiment["engine"]
        configurator_class, _, _ = _load_engine(experiment["engine"])
        return configurator_class(
            self.host,
            collection_params={**experiment.get("collection_params", {})},
            connection_params={**experiment.get("connection_params", {})},
        )

    def _create_uploader(self, experiment) -> BaseUploader:
        _, uploader_class, _ = _load_engine(experiment["engine"])
        return uploader_class(
            self.host,
            connection_params={**experiment.get("connection_params", {})},
            upload_params={**experiment.get("upload_params", {})},
        )

    def _create_searchers(self, experiment) -> List[BaseSearcher]:
        _, _, searcher_class = _load_engine(experiment["engine"])
        return [
            searcher_class(
                self.host,
                connection_params={**experiment.get("connection_params", {})},
                search_params=search_params,
            )
            for search_params in experiment.get("search_params", [{}])
        ]

    def build_client(self, experiment):
        return BaseClient(
            name=experiment["name"],
            engine=experiment["engine"],
            configurator=self._create_configurator(experiment),
            uploader=self._create_uploader(experiment),
            searchers=self._create_searchers(experiment),
        )
