from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.mongodb.config import (
    get_mongo_client,
    EMBEDDING_FIELD_NAME,
    ATLAS_COLLECTION_NAME,
    ATLAS_VECTOR_SEARCH_INDEX_NAME,
    ATLAS_DB_NAME,
)
import time


class MongoConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "euclidean",
        Distance.COSINE: "cosine",
        Distance.DOT: "dotProduct",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self.client = get_mongo_client(host, connection_params)
        self.db = self.client[ATLAS_DB_NAME]
        self.collection = self.db[ATLAS_COLLECTION_NAME]

    def clean(self):
        index_exists = True
        try_count = 1

        while index_exists is True:
            index_exists = False
            print(
                f"Ensuring the search index named {ATLAS_VECTOR_SEARCH_INDEX_NAME} does not exist..."
            )
            try:
                self.collection.drop_search_index(ATLAS_VECTOR_SEARCH_INDEX_NAME)
            except Exception as e:
                if "IndexNotFound" in e.__str__():
                    pass
                else:
                    print(e)

            stats = self.db.command("collstats", self.collection.name)
            # Print the index details
            index_details = stats.get("indexDetails", {})
            index_exists = False
            for index_name, details in index_details.items():
                if ATLAS_VECTOR_SEARCH_INDEX_NAME in index_name:
                    print(f"Still detected index. Stats: {details}")
                    index_exists = True
            try_count = try_count + 1
            # sleep for 10 seconds to avoid invalid state
            time.sleep(10)

        print(
            f"Finished ensuring the search index does not exist... after {try_count} tries"
        )

        print("Ensuring the collection does not exist...")

        collection_exists = True
        while collection_exists is True:
            try_count = try_count + 1
            try:
                self.db.drop_collection(ATLAS_COLLECTION_NAME)
            except Exception as e:
                if "not exist" in e.__str__():
                    pass
                else:
                    print(e)
            collection_exists = False
            collection_names = self.db.list_collection_names()
            for collection_name in collection_names:
                if ATLAS_COLLECTION_NAME in collection_name:
                    print(
                        f"Still detected collection named {ATLAS_COLLECTION_NAME}. Trying again..."
                    )
                    collection_exists = True
            # sleep for 10 seconds to avoid invalid state
            time.sleep(10)
        print(
            f"Finished ensuring the collection does not exist... after {try_count} tries"
        )

    def recreate(self, dataset: Dataset, collection_params):
        # Explicitly create a collection in a MongoDB database.
        print(f"Explicitly creating a collection named {ATLAS_COLLECTION_NAME}...")
        self.db.create_collection(ATLAS_COLLECTION_NAME)
        self.collection = self.db[ATLAS_COLLECTION_NAME]
        print(
            f"Creating the search index with vector mapping named {ATLAS_VECTOR_SEARCH_INDEX_NAME}..."
        )

        self.collection.create_search_index(
            {
                "definition": {
                    "mappings": {
                        "dynamic": True,
                        "fields": {
                            EMBEDDING_FIELD_NAME: {
                                "dimensions": dataset.config.vector_size,
                                "similarity": self.DISTANCE_MAPPING[
                                    dataset.config.distance
                                ],
                                "type": "knnVector",
                            }
                        },
                    }
                },
                "name": ATLAS_VECTOR_SEARCH_INDEX_NAME,
            }
        )
        pass
