import time
from multiprocessing import Pool

from weaviate import Client

from utils import JSONFileConverter


class Querier:
    client = None
    schema = None

    @classmethod
    def init_client(cls, schema):
        cls.schema = schema
        cls.client = Client("http://weaviate_server")

    @classmethod
    def search_one(cls, vector):
        top = 10
        near_vector = {"vector": vector}
        start = time.monotonic()
        (
            cls.client.query.get(cls.schema, ["_additional {id certainty}"])
            .with_near_vector(near_vector)
            .with_limit(top)
            .do()
        )
        end = time.monotonic()
        return end - start


class Searcher:
    def __init__(self, data, schema, data_converter=JSONFileConverter):
        """

        :param data: benchmark data
        """
        self.schema = schema
        self.data = data_converter(data)
        self.client = Client("http://weaviate_server")

    def search_one(self, vector):
        Querier.client = self.client
        Querier.schema = self.schema
        return Querier.search_one(vector)

    def search_all(self, parallel):
        print(f"Search with {parallel} threads")

        if parallel == 1:
            for vector in self.data:
                print(f"search::latency = {self.search_one(vector)}")
        else:
            with Pool(
                processes=parallel,
                initializer=Querier.init_client,
                initargs=(self.schema,),
            ) as pool:
                for latency in pool.imap_unordered(
                    Querier.search_one,
                    iterable=self.data,
                ):
                    print(f"search::latency = {latency}")
