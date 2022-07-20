from pathlib import Path
from datetime import datetime
from multiprocessing import Pool
from typing import Text

import typer
from tqdm import tqdm
from weaviate import Client

from searcher import Searcher
from uploader import Uploader
from utils import iter_batches, JSONFileConverter


DATA_PATH = Path("/dataset")
SCHEMA = {
    "class": "Bench",
    "vectorizer": "none",
    "properties": [],
    "vectorIndexConfig": {
        "ef": 100,
        "efConstruction": 100,
        "maxConnections": 32,
        "vectorCacheMaxObjects": 1000000000,
        "distance": "cosine",
    },
}

app = typer.Typer()


@app.command()
def configure():
    """
    Sets up the engine by creating a new Weaviate class with selected
    configuration. Each call to that function recreates the config and removes
    all the existing configuration and its data.
    """
    client = Client("http://weaviate_server")
    start = datetime.now()
    classes = client.schema.get()

    for cl in classes["classes"]:
        if cl["class"] == SCHEMA["class"]:
            client.schema.delete_class(SCHEMA["class"])

    client.schema.create_class(SCHEMA)
    time_spent = datetime.now() - start
    print(f"configure::latency = {time_spent.total_seconds()}")


@app.command()
def load(filename: Text, batch_size: int, parallel=1):
    # Insert all the points in batches of selected size
    with open(DATA_PATH / filename, "r") as fp:
        with Pool(
            processes=parallel, initializer=Uploader.init_client, initargs=()
        ) as pool:
            res = pool.imap(
                Uploader.update, iter_batches(JSONFileConverter(fp), batch_size)
            )
            for batch_res in tqdm(res):
                print(f"load::latency = {batch_res}")


@app.command()
def search(filename: Text, parallel=4):
    with open(DATA_PATH / filename, "r") as fp:
        searcher = Searcher(fp, SCHEMA["class"])
        searcher.search_all(parallel=parallel)


if __name__ == "__main__":
    app()
