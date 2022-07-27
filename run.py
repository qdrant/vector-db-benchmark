import fnmatch
import glob
import json
import os

import typer

from benchmark import DATASETS_DIR
from benchmark.dataset import Dataset
from benchmark.settings import ROOT_DIR
from engine.clients.client_factory import ClientFactory


app = typer.Typer()


def read_engine_configs() -> dict:
    all_configs = {}
    engines_config_dir = os.path.join(ROOT_DIR, "experiments", "configurations")
    config_files = glob.glob(os.path.join(engines_config_dir, "*.json"))
    for config_file in config_files:
        with open(config_file, "r") as fd:
            configs = json.load(fd)
            for config in configs:
                all_configs[config["name"]] = config

    return all_configs


def read_dataset_config():
    all_configs = {}
    datasets_config_path = DATASETS_DIR / "datasets.json"
    with open(datasets_config_path, "r") as fd:
        configs = json.load(fd)
        for config in configs:
            all_configs[config["name"]] = config
    return all_configs


@app.command()
def run(engines: str = "*", datasets: str = "*", host: str = "localhost"):
    """
    Example:
        python3 run --engines *-m-16-* --datasets glove-*
    """
    all_engines = read_engine_configs()
    all_datasets = read_dataset_config()

    selected_engines = {
        name: config
        for name, config in all_engines.items()
        if fnmatch.fnmatch(name, engines)
    }
    selected_datasets = {
        name: config
        for name, config in all_datasets.items()
        if fnmatch.fnmatch(name, datasets)
    }

    for engine_name, engine_config in selected_engines.items():
        for dataset_name, dataset_config in selected_datasets.items():
            print(f"Running experiment: {engine_name} - {dataset_name}")
            client = ClientFactory(host).build_client(engine_config)
            dataset = Dataset(dataset_config)
            dataset.download()
            client.run_experiment(dataset)


if __name__ == "__main__":
    app()
