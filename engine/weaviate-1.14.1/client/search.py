from weaviate import Client

from engine.base_client.search import BaseSearcher


class WeaviateSearcher(BaseSearcher):
    @classmethod
    def init_client(cls, url, collection_name, ef=None, **_):
        cls.client = Client(url)
        cls.collection = collection_name
        if ef is not None:
            cls.client.schema.update_config({"vectorIndexConfig": {"ef": ef}})

    @classmethod
    def search_one(cls, vector, _):
        top = 10
        near_vector = {"vector": vector}
        res = (
            cls.client.query.get(cls.collection, ["_additional {id certainty}"])
            .with_near_vector(near_vector)
            .with_limit(top)
            .do()
        )
        return res
