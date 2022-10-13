import glob
import json
import os

from benchmark import DATASETS_DIR, ROOT_DIR


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
