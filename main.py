import logging
from typing import Text, Callable

import typer

from benchmark.backend.docker import DockerBackend
from benchmark.collector import LogCollector
from benchmark.dataset import Dataset
from benchmark.engine import Engine

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Configure the main Typer app
app = typer.Typer()

# If a specific command requires subcommands, it can be configured like:
# https://typer.tiangolo.com/tutorial/subcommands/single-file/
client_app = typer.Typer()
app.add_typer(client_app, name="run-client")


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


@client_app.command()
def load(
    engine_name: Text,
    dataset_name: Text,
    container_name: Text = "client",
):
    # Run the client process using selected backend and with a dataset mounted
    engine = Engine.from_name(engine_name)
    dataset = Dataset.from_name(dataset_name)
    with DockerBackend() as backend:
        # TODO: get rid of hardcoded paths, make them configurable
        client = backend.initialize_client(engine, container_name)
        client.mount(dataset.root_dir, "/dataset")
        client.run()

        log_collector = LogCollector()

        # TODO: select an operation to perform
        # Load all the files marked for load and collect the logs
        for filename in dataset.config.load:
            logger.info("Loading file %s", filename)
            logs = client.load_data(filename)
            log_collector.append(logs)

        # Iterate the kpi results and calculate statistics
        # TODO: that should be flexible and configurable from outside
        for kpi, values in log_collector.collect().items():
            print(f"sum({kpi}) =", sum(values))
            print(f"count({kpi}) =", len(values))
            print(f"mean({kpi}) =", sum(values) / len(values))


@client_app.command()
def search(
    engine_name: Text,
    dataset_name: Text,
    container_name: Text = "client",
    operation: Text = "load",
):
    # Run the client process using selected backend and with a dataset mounted
    engine = Engine.from_name(engine_name)
    dataset = Dataset.from_name(dataset_name)
    with DockerBackend() as backend:
        # TODO: get rid of hardcoded paths, make them configurable
        client = backend.initialize_client(engine, container_name)
        client.mount(dataset.root_dir, "/dataset")
        client.run()

        log_collector = LogCollector()

        # TODO: select an operation to perform
        # Load all the files marked for load and collect the logs
        for filename in dataset.config.load:
            logger.info("Loading file %s", filename)
            logs = client.search(filename)
            log_collector.append(logs)

        # Iterate the kpi results and calculate statistics
        # TODO: that should be flexible and configurable from outside
        for kpi, values in log_collector.collect().items():
            logger.info("sum(%s) = %f", kpi, sum(values))
            logger.info("count(%s) = %f", kpi, len(values))
            logger.info("mean(%s) = %f", kpi, sum(values) / len(values))


if __name__ == "__main__":
    app()
