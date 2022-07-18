import sys
import json
import logging
from typing import Text

import typer
from qdrant_client import QdrantClient
from datetime import datetime

from qdrant_client.http.models import Batch

logger = logging.getLogger(__name__)

# Connect to Qdrant server and create the collection for storing the points
client = QdrantClient(host="qdrant_server")
client.recreate_collection(
    collection_name="my_collection",
    vector_size=100,
    distance="Cosine",
)

app = typer.Typer()


@app.command()
def load(filename: Text):
    # Insert all the points one by one
    with open(f"/dataset/{filename}", "r") as fp:
        for i, line in enumerate(fp.readlines()):
            vector = json.loads(line)
            # Measure the time of each operation
            start = datetime.now()
            client.upsert(
                collection_name="my_collection",
                points=Batch(ids=[i], vectors=[vector]),
            )
            time = datetime.now() - start
            print(f"load::time = {time.total_seconds()}")


@app.command()
def search(filename: Text):
    # Insert all the points one by one
    with open(f"/dataset/{filename}", "r") as fp:
        for i, line in enumerate(fp.readlines()):
            vector = json.loads(line)
            # Measure the time of each operation
            start = datetime.now()
            results = client.search(
                collection_name="my_collection",
                query_vector=vector
            )
            time = datetime.now() - start
            print(f"search::time = {time.total_seconds()}")

            # TODO: check some metrics of the results, like recall


if __name__ == "__main__":
    app()
