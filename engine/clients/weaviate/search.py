from typing import Optional, Tuple, List

from weaviate import Client

from engine.base_client.search import BaseSearcher
from engine.clients.qdrant import QDRANT_COLLECTION_NAME
from engine.clients.weaviate import WEAVIATE_DEFAULT_PORT


class QdrantSearcher(BaseSearcher):
    search_params = {}
    client: Client = None

    @classmethod
    def init_client(cls, host, connection_params: dict, search_params: dict):
        url = f"http://{host}:{connection_params.pop('port', WEAVIATE_DEFAULT_PORT)}"
        cls.client = Client(url, **connection_params)
        cls.search_params = search_params

    @classmethod
    def conditions_to_filter(cls, _meta_conditions):
        # ToDo: implement
        return None

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        top = 10
        near_vector = {"vector": vector}
        res = (
            cls.client.query.get(cls.collection, ["_additional {id certainty}"])
            .with_near_vector(near_vector)
            .with_limit(top)
            .do()
        )
        res = cls.client.search(
            collection_name=QDRANT_COLLECTION_NAME,
            query_vector=vector,
            query_filter=cls.conditions_to_filter(meta_conditions),
            limit=top,
            **cls.search_params
        )

        return [(hit.id, hit.score) for hit in res]
