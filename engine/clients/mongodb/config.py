import os
from pymongo.mongo_client import MongoClient

MONGO_PORT = int(os.getenv("MONGO_PORT", 27017))
MONGO_AUTH = os.getenv("MONGO_AUTH", "performance")
MONGO_USER = os.getenv("MONGO_USER", "performance")
MONGO_READ_PREFERENCE = os.getenv("MONGO_READ_PREFERENCE", "primary")
MONGO_WRITE_CONCERN = os.getenv("MONGO_READ_PREFERENCE", "1")
EMBEDDING_FIELD_NAME = os.getenv("EMBEDDING_FIELD_NAME", "embedding")
EMBEDDING_DISTANCE = os.getenv("EMBEDDING_DISTANCE", None)
ATLAS_DB_NAME = os.getenv("ATLAS_DB_NAME", "vector-db")
ATLAS_COLLECTION_NAME = os.getenv("ATLAS_COLLECTION_NAME", "vector-collection")
ATLAS_VECTOR_SEARCH_INDEX_NAME = os.getenv(
    "ATLAS_VECTOR_SEARCH_INDEX_NAME", "vector-index"
)

# 90 seconds timeout
MONGO_QUERY_TIMEOUT = int(os.getenv("MONGO_QUERY_TIMEOUT", 90 * 1000))


def get_mongo_client(host, connection_params):
    user = MONGO_USER
    auth = MONGO_AUTH
    uri = f"mongodb+srv://{user}:{auth}@{host}/?retryWrites=true&w={MONGO_WRITE_CONCERN}&appName=vector-db-benchmark&readPreference={MONGO_READ_PREFERENCE}"
    # Create a new client and connect to the server
    client = MongoClient(uri)
    # Send a ping to confirm a successful connection
    try:
        client.admin.command("ping")
    except Exception as e:
        print(f"Failed pinging the deployment... error {e}")
    return client
