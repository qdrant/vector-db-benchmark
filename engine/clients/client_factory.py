from abc import ABC
from typing import List, Type

from engine.base_client.client import (
    BaseClient,
    BaseConfigurator,
    BaseSearcher,
    BaseUploader,
)
from engine.clients.elasticsearch import (
    ElasticConfigurator,
    ElasticSearcher,
    ElasticUploader,
)
from engine.clients.milvus import MilvusConfigurator, MilvusSearcher, MilvusUploader
from engine.clients.opensearch import (
    OpenSearchConfigurator,
    OpenSearchSearcher,
    OpenSearchUploader,
)
from engine.clients.pgvector import (
    PgVectorConfigurator,
    PgVectorSearcher,
    PgVectorUploader,
)
from engine.clients.qdrant import QdrantConfigurator, QdrantSearcher, QdrantUploader
from engine.clients.redis import RedisConfigurator, RedisSearcher, RedisUploader
from engine.clients.weaviate import (
    WeaviateConfigurator,
    WeaviateSearcher,
    WeaviateUploader,
)
from engine.clients.doris import (
    DorisConfigurator,
    DorisSearcher,
    DorisUploader,
)

ENGINE_CONFIGURATORS = {
    "qdrant": QdrantConfigurator,
    "weaviate": WeaviateConfigurator,
    "milvus": MilvusConfigurator,
    "elasticsearch": ElasticConfigurator,
    "opensearch": OpenSearchConfigurator,
    "redis": RedisConfigurator,
    "pgvector": PgVectorConfigurator,
    "doris": DorisConfigurator,
}

ENGINE_UPLOADERS = {
    "qdrant": QdrantUploader,
    "weaviate": WeaviateUploader,
    "milvus": MilvusUploader,
    "elasticsearch": ElasticUploader,
    "opensearch": OpenSearchUploader,
    "redis": RedisUploader,
    "pgvector": PgVectorUploader,
    "doris": DorisUploader,
}

ENGINE_SEARCHERS = {
    "qdrant": QdrantSearcher,
    "weaviate": WeaviateSearcher,
    "milvus": MilvusSearcher,
    "elasticsearch": ElasticSearcher,
    "opensearch": OpenSearchSearcher,
    "redis": RedisSearcher,
    "pgvector": PgVectorSearcher,
    "doris": DorisSearcher,
}


class ClientFactory(ABC):
    def __init__(self, host):
        self.host = host
        self.engine = None

    def _create_configurator(self, experiment) -> BaseConfigurator:
        self.engine = experiment["engine"]
        engine_configurator_class = ENGINE_CONFIGURATORS[experiment["engine"]]
        engine_configurator = engine_configurator_class(
            self.host,
            collection_params={**experiment.get("collection_params", {})},
            connection_params={**experiment.get("connection_params", {})},
        )
        return engine_configurator

    def _create_uploader(self, experiment) -> BaseUploader:
        engine_uploader_class = ENGINE_UPLOADERS[experiment["engine"]]
        upload_params = {**experiment.get("upload_params", {})}
        # Propagate collection_params for engines that need database/table info during upload (e.g., doris)
        if experiment["engine"] == "doris":
            merged_collection = {
                **experiment.get("collection_params", {}),
                **upload_params.get("collection_params", {}),
            }
            upload_params["collection_params"] = merged_collection
        engine_uploader = engine_uploader_class(
            self.host,
            connection_params={**experiment.get("connection_params", {})},
            upload_params=upload_params,
        )
        return engine_uploader

    def _create_searchers(self, experiment) -> List[BaseSearcher]:
        engine_searcher_class: Type[BaseSearcher] = ENGINE_SEARCHERS[
            experiment["engine"]
        ]
        engine_searchers = []
        for search_params in experiment.get("search_params", [{}]):
            params = {**search_params}
            if experiment["engine"] == "doris":
                merged_collection = {
                    **experiment.get("collection_params", {}),
                    **params.get("collection_params", {}),
                }
                params["collection_params"] = merged_collection
            engine_searchers.append(
                engine_searcher_class(
                    self.host,
                    connection_params={**experiment.get("connection_params", {})},
                    search_params=params,
                )
            )

        return engine_searchers

    def build_client(self, experiment):
        return BaseClient(
            name=experiment["name"],
            engine=experiment["engine"],
            configurator=self._create_configurator(experiment),
            uploader=self._create_uploader(experiment),
            searchers=self._create_searchers(experiment),
        )
