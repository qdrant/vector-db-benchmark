import copy
from typing import List, Tuple

from engine.base_client.distances import Distance
from engine.base_client.search import BaseSearcher
from engine.clients.mongodb.config import (
    ATLAS_COLLECTION_NAME,
    ATLAS_DB_NAME,
    ATLAS_VECTOR_SEARCH_INDEX_NAME,
    EMBEDDING_FIELD_NAME,
    get_mongo_client,
)


class MongoSearcher(BaseSearcher):
    search_params = {}
    client = None

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.distance = distance
        cls.client = get_mongo_client(host, connection_params)
        cls.search_params = copy.deepcopy(search_params)

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        numCandidates = cls.search_params.pop("numCandidates", 100)
        # define pipeline

        pipeline = [
            {
                "$vectorSearch": {
                    "index": ATLAS_VECTOR_SEARCH_INDEX_NAME,
                    "path": EMBEDDING_FIELD_NAME,
                    "queryVector": vector,
                    "numCandidates": numCandidates,
                    "limit": top,
                }
            },
            {
                "$project": {
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        # run pipeline
        results = cls.client[ATLAS_DB_NAME][ATLAS_COLLECTION_NAME].aggregate(pipeline)
        search_result = []
        for result in results:
            reverted_normalization_score = float(result["score"])
            # In MongoDB Atlas, for cosine and dotProduct similarities,
            # the normalization of the score is done using the following formula:
            # score = (1 + cosine/dot_product(v1,v2)) / 2
            # to revert it we simply do:
            if cls.distance == Distance.COSINE or cls.distance == Distance.L2:
                reverted_normalization_score = (2.0 * reverted_normalization_score) - 1
            search_result.append((int(result["_id"]), reverted_normalization_score))

        return search_result
