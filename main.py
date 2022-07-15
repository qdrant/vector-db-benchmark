import logging
from enum import Enum
from typing import Text, Callable

import typer

from benchmark.backend.docker import DockerBackend
from benchmark.collector import LogCollector
from benchmark.dataset import Dataset
from benchmark.engine import Engine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Configure the main app. If a specific command requires subcommands, it can be
# configured with: https://typer.tiangolo.com/tutorial/subcommands/single-file/
app = typer.Typer()


@app.command()
def run_server(
    engine_name: Text,
    container_name: Text = "server",
):
    # Run the server process using selected backend
    engine = Engine.from_name(engine_name)
    with DockerBackend() as backend:
        server = backend.initialize_server(engine, container_name)
        server.run()
        for log_entry in server.logs():
            print(log_entry)


class ClientOperation(Enum):
    LOAD = "load"
    SEARCH = "search"


@app.command()
def run_client(
    engine_name: Text,
    operation: ClientOperation,
    dataset_name: Text,
    container_name: Text = "client",
):
    # Load engine and dataset configuration from the .json config files
    engine = Engine.from_name(engine_name)
    dataset = Dataset.from_name(dataset_name)

    # Run the client process using selected backend and with a dataset mounted
    log_collector = LogCollector()
    with DockerBackend() as backend:
        # Mount selected dataset content
        client = backend.initialize_client(engine, container_name)
        client.mount(dataset.root_dir, "/dataset")
        client.run()

        if ClientOperation.LOAD == operation:
            # Load all the files marked for load and collect the logs
            for filename in dataset.config.load.files:
                logger.info("Loading file %s", filename)
                logs = client.load_data(filename)
                log_collector.append(logs)
        if ClientOperation.SEARCH == operation:
            # Search the points from the selected files
            for filename in dataset.config.search.files:
                logger.info("Loading file %s", filename)
                logs = client.load_data(filename)
                log_collector.append(logs)

        # Iterate the kpi results and calculate statistics
        for kpi, values in log_collector.collect().items():
            print(f"sum({kpi}) =", sum(values))
            print(f"count({kpi}) =", len(values))
            print(f"mean({kpi}) =", sum(values) / len(values))


if __name__ == "__main__":
    app()
