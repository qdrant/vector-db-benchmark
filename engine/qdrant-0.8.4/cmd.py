import json
import logging
import sys
from datetime import datetime

from qdrant_client import QdrantClient
from qdrant_client.http.models import Batch

logger = logging.getLogger(__name__)

# Connect to Qdrant server and create the collection for storing the points
client = QdrantClient(host="qdrant_server")
client.recreate_collection(
    collection_name="my_collection",
    vector_size=100,
    distance="Cosine",
)

if sys.argv[1] == "load":
    # Insert all the points one by one
    with open(f"/dataset/{sys.argv[2]}", "r") as fp:
        for i, line in enumerate(fp.readlines()):
            vector = json.loads(line)
            # Measure the time of each operation
            start = datetime.now()
            client.upsert(
                collection_name="my_collection",
                points=Batch(ids=[i], vectors=[vector]),
            )
            time = datetime.now() - start
            print(f"{sys.argv[1]}::time = {time.total_seconds()}")
else:
    print(f"Unknown command {sys.argv[1]}")
