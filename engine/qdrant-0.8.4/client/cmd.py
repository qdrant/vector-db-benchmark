import json
import logging
from typing import Text, Any, Iterable, TextIO

import typer
from qdrant_client import QdrantClient
from datetime import datetime

from qdrant_client.http.models import Batch

logger = logging.getLogger(__name__)

# Connect to Qdrant server and create the collection for storing the points
client = QdrantClient(host="qdrant_server")

app = typer.Typer()


def iter_batches(fp: TextIO, n: int) -> Iterable[Any]:
    batch = []
    while True:
        line = fp.readline()
        if line is None:
            break
        batch.append(json.loads(line))
        if len(batch) >= n:
            yield batch
            batch = []
    if len(batch) > 0:
        yield batch


@app.command()
def configure(vector_size: int, distance: Text):
    """
    Sets up the engine by creating a new Qdrant collection with selected
    configuration. Each call to that function recreates the config and removes
    all the existing configuration and its data.
    :param vector_size:
    :param distance:
    :return:
    """
    start = datetime.now()
    client.recreate_collection(
        collection_name="my_collection",
        vector_size=vector_size,
        distance=distance,
    )
    time_spent = datetime.now() - start
    print(f"configure::latency = {time_spent.total_seconds()}")


@app.command()
def load(filename: Text, batch_size: int):
    # Insert all the points in batches of selected size
    with open(f"/dataset/{filename}", "r") as fp:
        for i, batch in enumerate(iter_batches(fp, batch_size)):
            # Generate the ids, as they're not provided
            start_id = batch_size * i
            ids = list(range(start_id, start_id + batch_size))
            # Measure the time of each operation
            start = datetime.now()
            client.upsert(
                collection_name="my_collection",
                points=Batch(ids=ids, vectors=batch),
            )
            time_spent = datetime.now() - start
            print(f"load::latency = {time_spent.total_seconds()}")


@app.command()
def search(filename: Text):
    # Insert all the points one by one
    with open(f"/dataset/{filename}", "r") as fp:
        while True:
            line = fp.readline()
            vector = json.loads(line)
            # Measure the time of each operation
            start = datetime.now()
            results = client.search(
                collection_name="my_collection",
                query_vector=vector
            )
            time = datetime.now() - start
            print(f"search::latency = {time.total_seconds()}")
            # TODO: check some metrics of the results, like recall


if __name__ == "__main__":
    app()
