import fnmatch
import traceback
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import List, Optional

import typer

from benchmark.config_read import read_dataset_config, read_engine_configs
from benchmark.dataset import Dataset
from engine.base_client import IncompatibilityError
from engine.clients.client_factory import ClientFactory

app = typer.Typer()


@app.command()
def run(
    engines: List[str] = typer.Option(["*"]),
    datasets: List[str] = typer.Option(["*"]),
    host: str = typer.Option("localhost"),
    skip_upload: bool = typer.Option(False),
    skip_search: bool = typer.Option(False),
    skip_if_exists: bool = typer.Option(False),
    exit_on_error: bool = typer.Option(True),
    timeout: float = typer.Option(86400.0),
    skip_configure: bool = typer.Option(False),
):
    """
    Examples:

    python3 run.py --engines "qdrant-rps-m-*-ef-*" --datasets "dbpedia-openai-100K-1536-angular" # Qdrant RPS mode

    python3 run.py --engines "*-m-*-ef-*" --datasets "glove-*" # All engines and their configs for glove datasets
    """
    all_engines = read_engine_configs()
    all_datasets = read_dataset_config()

    selected_engines = {
        name: config
        for name, config in all_engines.items()
        if any(fnmatch.fnmatch(name, engine) for engine in engines)
    }
    selected_datasets = {
        name: config
        for name, config in all_datasets.items()
        if any(fnmatch.fnmatch(name, dataset) for dataset in datasets)
    }

    for engine_name, engine_config in selected_engines.items():
        for dataset_name, dataset_config in selected_datasets.items():
            print(f"Running experiment: {engine_name} - {dataset_name}")
            client = ClientFactory(host).build_client(engine_config)
            try:

                dataset = Dataset(dataset_config)
                if dataset.config.type == "sparse" and not client.sparse_vector_support:
                    raise IncompatibilityError(
                        f"{client.name} engine does not support sparse vectors"
                    )
                dataset.download()

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        client.run_experiment,
                        dataset,
                        skip_upload,
                        skip_search,
                        skip_if_exists,
                        skip_configure,
                    )
                    try:
                        future.result(timeout=timeout)
                    except FuturesTimeoutError:
                        # If the timeout is reached, the server might be still in the
                        # middle of some background processing, like creating the index.
                        # Next experiment should not be launched. It's better to reset
                        # the server state manually.
                        print(
                            f"Timed out {engine_name} - {dataset_name}, "
                            f"exceeded {timeout} seconds"
                        )
                        exit(2)
                client.delete_client()
            except IncompatibilityError as e:
                print(
                    f"Skipping {engine_name} - {dataset_name}, incompatible params:", e
                )
                continue
            except KeyboardInterrupt:
                traceback.print_exc()
                exit(1)
            except Exception as e:
                print(f"Experiment {engine_name} - {dataset_name} interrupted")
                traceback.print_exc()
                if exit_on_error:
                    raise e
                continue


if __name__ == "__main__":
    app()
