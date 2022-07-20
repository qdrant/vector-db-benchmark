import logging
from typing import Optional, Text

import typer

from benchmark.cli import BackendType, ClientOperation, run_backend
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
    backend_type: BackendType = BackendType.LOCAL,
    docker_host: Optional[Text] = None,
):
    # Run the server process using selected backend
    engine = Engine.from_name(engine_name)
    with run_backend(backend_type, docker_host=docker_host) as backend:
        server = backend.initialize_server(engine, container_name)
        server.run()
        for log_entry in server.logs():
            print(log_entry)


@app.command()
def run_client(
    engine_name: Text,
    operation: ClientOperation,
    dataset_name: Text,
    container_name: Text = "client",
    batch_size: int = 64,
    server_host: Optional[Text] = None,
    backend_type: BackendType = BackendType.LOCAL,
    docker_host: Optional[Text] = None,
):
    # Load engine and dataset configuration from the .json config files
    engine = Engine.from_name(engine_name)
    dataset = Dataset.from_name(dataset_name)

    # Run the client process using selected backend and with a dataset mounted
    log_collector = LogCollector()
    with run_backend(backend_type, docker_host=docker_host) as backend:
        # Download the dataset if it's not present
        # TODO: download the dataset on container level (remote issues)
        if not dataset.is_ready():
            logger.info("Downloading the dataset %s", dataset.name)
            dataset.download()

        # Build environmental variables to be passed to client
        environment = {
            "SERVER_HOST": server_host,
        }

        # Mount selected dataset content
        client = backend.initialize_client(engine, container_name)
        client.mount(dataset.root_dir, "/dataset")
        client.run(environment)

        if ClientOperation.CONFIGURE == operation:
            # Load all the files marked for load and collect the logs
            logger.info("Configuring the engine: %s", dataset.config)
            logs = client.configure(dataset.config.size, dataset.config.distance)
            log_collector.append(logs)

        if ClientOperation.LOAD == operation:
            if len(dataset.config.load.files) == 0:
                logger.warning(
                    "None of the files has been set for the load operation. "
                    "Please make sure some data is loaded into the engine."
                )

            # Load all the files marked for load and collect the logs
            for filename in dataset.config.load.files:
                logger.info("Loading file %s", filename)
                logs = client.load_data(filename, batch_size)
                log_collector.append(logs)

        if ClientOperation.SEARCH == operation:
            if len(dataset.config.search.files) == 0:
                logger.warning(
                    "None of the files has been set for the search operation."
                )

            # Search the points from the selected files
            for filename in dataset.config.search.files:
                logger.info("Loading file %s", filename)
                logs = client.search(filename)
                log_collector.append(logs)

        # Iterate the kpi results and calculate statistics
        logger.info("Starting log aggregation of client outputs")
        for kpi, values in log_collector.collect().items():
            print(f"sum({kpi}) =", sum(values))
            print(f"count({kpi}) =", len(values))
            print(f"mean({kpi}) =", sum(values) / len(values))


if __name__ == "__main__":
    app()
