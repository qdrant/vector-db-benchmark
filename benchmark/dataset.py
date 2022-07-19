import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Text

import jsons

from benchmark import BASE_DIRECTORY


@dataclass
class PhaseConfig:
    files: List[Text] = field(default_factory=list)
    engine: Dict[Any, Any] = field(default_factory=dict)


@dataclass
class DatasetConfig:
    size: int
    distance: Text
    load: PhaseConfig
    search: PhaseConfig
    url: Optional[Text]


class Dataset:
    @classmethod
    def from_name(cls, name: Text) -> "Dataset":
        config_path = BASE_DIRECTORY / "dataset" / name / "config.json"
        with open(config_path, "r") as fp:
            config = jsons.load(json.load(fp), DatasetConfig)
        return Dataset(name, config)

    def __init__(self, name: Text, config: DatasetConfig):
        self.name = name
        self.config = config

    @property
    def root_dir(self) -> Path:
        return BASE_DIRECTORY / "dataset" / self.name

    def is_ready(self):
        root_dir = self.root_dir
        return all(
            (root_dir / filename).exists() for filename in self.config.load.files
        )

    def download(self):
        """
        Download the dataset and put it into the directory.
        :return:
        """
        import importlib
        import sys

        sys.path.insert(0, str(self.root_dir))
        importlib.import_module("download")
