import time
from typing import List, Optional

from pymongo import InsertOne

from engine.base_client.upload import BaseUploader
from engine.clients.mongodb.config import (
    ATLAS_COLLECTION_NAME,
    ATLAS_DB_NAME,
    ATLAS_VECTOR_SEARCH_INDEX_NAME,
    EMBEDDING_FIELD_NAME,
    get_mongo_client,
)


class MongoUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.client = get_mongo_client(host, connection_params)
        cls.upload_params = upload_params
        # Getting the database instance
        cls.db = cls.client[ATLAS_DB_NAME]
        # Creating a collection
        cls.collection = cls.db[ATLAS_COLLECTION_NAME]

    @classmethod
    def upload_batch(
        cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]
    ):
        # Update the collection with the embeddings
        requests = []

        for i in range(len(ids)):
            doc_id = ids[i]
            embedding = vectors[i]
            doc = {}
            doc["_id"] = doc_id
            doc[EMBEDDING_FIELD_NAME] = embedding
            requests.append(InsertOne(doc))

        cls.collection.bulk_write(requests)

    @classmethod
    def post_upload(cls, _distance):
        print("waiting for search index status to be Active")

        queryable = False
        status = "n/a"
        try_count = 1
        while status != "ACTIVE" and queryable is False:
            print(f"checking search indices. try: {try_count}...")
            search_indexes = cls.collection.list_search_indexes()
            for search_index in search_indexes:
                index_name = search_index["name"]
                if index_name == ATLAS_VECTOR_SEARCH_INDEX_NAME:
                    print(
                        f"detected search index named {ATLAS_VECTOR_SEARCH_INDEX_NAME}. checking status..."
                    )
                    print(search_index)
                    queryable = search_index["queryable"]
                    status = search_index["status"]
            try_count = try_count + 1
        print(
            f"Finished waiting for search index status={status} and queryable={queryable}."
        )
        return {}

    @classmethod
    def get_memory_usage(cls):
        return {}
