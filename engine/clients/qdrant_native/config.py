import os

QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "benchmark")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
