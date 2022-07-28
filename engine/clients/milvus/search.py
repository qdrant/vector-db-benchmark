from typing import List, Tuple

from pymilvus import Collection, connections

from engine.base_client.search import BaseSearcher
from engine.clients.milvus.config import (
    MILVUS_COLLECTION_NAME,
    MILVUS_DEFAULT_ALIAS,
    MILVUS_DEFAULT_PORT,
)


class MilvusSearcher(BaseSearcher):
    search_params = {}
    client: connections = None
    collection: Collection = None

    @classmethod
    def init_client(cls, host, connection_params: dict, search_params: dict):
        cls.client = connections.connect(
            alias=MILVUS_DEFAULT_ALIAS,
            host=host,
            port=str(connection_params.pop("port", MILVUS_DEFAULT_PORT)),
            **connection_params
        )
        cls.collection = Collection(MILVUS_COLLECTION_NAME, using=MILVUS_DEFAULT_ALIAS)
        cls.search_params = search_params

    @classmethod
    def conditions_to_filter(cls, _meta_conditions):
        # ToDo: implement
        return None

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        res = cls.collection.search(
            data=[vector],
            anns_field="vector",
            param=cls.search_params,
            limit=top,
        )

        return list(zip(res[0].ids, res[0].distances))
