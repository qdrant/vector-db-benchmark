import json
import logging
from datetime import datetime
from typing import TextIO, Iterable, Any, Text

import urllib3
from elasticsearch import Elasticsearch, NotFoundError
import config
import typer

logger = logging.getLogger(__name__)


# That has to be done, so Elasticsearch client doesn't break on SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

client = Elasticsearch(
    f"http://{config.ELASTIC_HOST}:{config.ELASTIC_PORT}",
    basic_auth=(config.ELASTIC_USER, config.ELASTIC_PASSWORD),
    verify_certs=False,
    request_timeout=90,
    retry_on_timeout=True,
)
app = typer.Typer()


def iter_batches(fp: TextIO, n: int) -> Iterable[Any]:
    batch = []
    while True:
        line = fp.readline()
        if line is None or len(line) == 0:
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
    # See: https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html#dense-vector-params
    mappings = {
        "properties": {
            "vector": {
                "type": "dense_vector",
                "dims": vector_size,
                "index": True,
                "similarity": distance.lower(),
                "index_options": {
                    "type": "hnsw",
                    "m": 16,
                    "ef_construction": 100,
                },
            }
        }
    }

    start = datetime.now()
    try:
        client.indices.delete(index=config.ELASTIC_INDEX)
    except NotFoundError:
        pass
    client.indices.create(index=config.ELASTIC_INDEX, mappings=mappings)
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
            # Prepare a list of Elastic operations
            operations = []
            for vector_id, vector in zip(ids, batch):
                operations.append({"index": {"_id": vector_id}})
                operations.append({"vector": vector})
            # Measure the time of each operation
            start = datetime.now()
            client.bulk(
                index=config.ELASTIC_INDEX,
                operations=operations,
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
            # TODO: make k and num_candidates parameters
            client.knn_search(
                index=config.ELASTIC_INDEX,
                knn={
                    "field": "vector",
                    "query_vector": vector,
                    "k": 10,
                    "num_candidates": 100,
                },
            )
            time = datetime.now() - start
            print(f"search::latency = {time.total_seconds()}")
            # TODO: check some metrics of the results, like recall


if __name__ == "__main__":
    app()
