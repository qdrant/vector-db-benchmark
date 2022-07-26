import os
from typing import Text

import typer

from engine.base_client.client import BaseClient
from engine.base_client.distances import Distance
from configure import WeaviateConfigurator
from search import WeaviateSearcher
from upload import WeaviateUploader


SERVER_HOST = os.environ.get("SERVER_HOST", "weaviate_server")
SERVER_PORT = int(os.environ.get("SERVER_PORT", 8080))
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"

app = typer.Typer()

client = BaseClient(
    SERVER_URL, WeaviateConfigurator, WeaviateUploader, WeaviateSearcher
)


@app.command()
def configure(
    collection_name, ef_construction, max_connections, distance, vector_size
):
    distance = Distance.from_name(distance)
    client.configure(collection_name, ef_construction, max_connections, distance, vector_size)


@app.command()
def load(collection_name: Text, filename: Text, batch_size: int, parallel: int):
    client.upload(collection_name, filename, batch_size, parallel)


@app.command()
def search(collection_name, filename, parallel):
    client.search_all(collection_name, filename, parallel)


if __name__ == "__main__":
    app()
