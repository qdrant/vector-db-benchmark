from typing import List, Tuple

from chromadb import ClientAPI, HttpClient, Settings
from chromadb.api.types import IncludeEnum

from dataset_reader.base_reader import Query
from engine.base_client.search import BaseSearcher
from engine.clients.chroma.config import CHROMA_COLLECTION_NAME, chroma_fix_host
from engine.clients.chroma.parser import ChromaConditionParser


class ChromaSearcher(BaseSearcher):
    client: ClientAPI = None
    parser = ChromaConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.client = HttpClient(
            host=chroma_fix_host(host),
            settings=Settings(allow_reset=True, anonymized_telemetry=False),
            **connection_params,
        )
        cls.collection = cls.client.get_collection(name=CHROMA_COLLECTION_NAME)
        cls.search_params = search_params

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        res = cls.collection.query(
            query_embeddings=[query.vector],
            n_results=top,
            where=cls.parser.parse(query.meta_conditions),
            include=[IncludeEnum.distances],
        )

        return [
            (int(hit[0]), float(hit[1]))
            for hit in zip(res["ids"][0], res["distances"][0])
        ]

    def setup_search(self):
        metadata = self.collection.metadata.copy()
        metadata.pop("hnsw:space", None)  # Not allowed in the collection.modify method
        metadata.update(self.search_params.get("config", {}))
        self.collection.modify(metadata=metadata)
