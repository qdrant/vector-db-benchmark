import logging
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
from typing import Text

import typer
from searcher import Searcher
from tqdm import tqdm
from uploader import Uploader
from utils import JSONFileConverter, iter_batches
from weaviate import Client

logger = logging.getLogger(__name__)

DATA_PATH = Path("/dataset")
SCHEMA_NAME = "Bench"
SERVER_HOSTNAME = "weaviate_server"
SERVER_PORT = 8080
SERVER_URL = f"http://{SERVER_HOSTNAME}:{SERVER_PORT}"

app = typer.Typer()


@app.command()
def configure(_, distance: Text):
    """
    Sets up the engine by creating a new Weaviate class with selected
    configuration. Each call to that function recreates the config and removes
    all the existing configuration and its data.
    """
    client = Client(SERVER_URL)
    classes = client.schema.get()

    for cl in classes["classes"]:
        if cl["class"] == SCHEMA_NAME:
            client.schema.delete_class(SCHEMA_NAME)

    schema = {
        "class": SCHEMA_NAME,
        "vectorizer": "none",
        "properties": [],
        "vectorIndexConfig": {
            "ef": 100,
            "efConstruction": 100,
            "maxConnections": 32,
            "vectorCacheMaxObjects": 1000000000,
            "distance": distance.lower(),
        },
    }

    start = datetime.now()
    client.schema.create_class(schema)
    time_spent = datetime.now() - start
    print(f"configure::latency = {time_spent.total_seconds()}")


@app.command()
def load(filename: Text, batch_size: int, parallel=4):
    # Insert all the points in batches of selected size
    with open(DATA_PATH / filename, "r") as fp:
        with Pool(
            processes=int(parallel),
            initializer=Uploader.init_client,
            initargs=(SERVER_URL,),
        ) as pool:
            res = pool.imap(
                Uploader.update, iter_batches(JSONFileConverter(fp), batch_size)
            )
            for batch_res in tqdm(res):
                print(f"load::latency = {batch_res}")


@app.command()
def search(filename: Text, parallel=4):
    with open(DATA_PATH / filename, "r") as fp:
        searcher = Searcher(SERVER_URL, fp, SCHEMA_NAME)
        searcher.search_all(parallel=int(parallel))


if __name__ == "__main__":
    app()
