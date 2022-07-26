import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Text, Union

from benchmark import BASE_DIRECTORY

EnvironmentalVariables = Dict[Text, Union[Text, int, bool]]


class ContainerRole(Enum):
    CLIENT = "client"
    SERVER = "server"


@dataclass
class ContainerConf:
    engine: Optional[Text] = None
    dataset: Optional[Text] = None
    image: Optional[Text] = None
    dockerfile: Optional[Text] = None
    environment: EnvironmentalVariables = field(default_factory=dict)
    main: Optional[Text] = None
    hostname: Optional[Text] = None
    ports: List[int] = field(default_factory=list)

    def dockerfile_path(self) -> Path:
        """
        Calculates the absolute root_dir to the directory containing the dockerfile,
        using given root directory as a base.
        :return:
        """
        if self.engine is not None:
            return BASE_DIRECTORY / "engine" / self.engine
        if self.dataset is not None:
            return BASE_DIRECTORY / "dataset" / self.dataset
        raise ValueError("Either engine or dataset property has to be set")


class Engine:
    """
    An abstraction over vector database engine.
    """

    @classmethod
    def from_name(cls, name: Text) -> "Engine":
        container_configs = {}
        with open(BASE_DIRECTORY / "engine" / name / "config.json", "r") as fp:
            config = json.load(fp)
            for container_name, conf in config.items():
                container_configs[container_name] = ContainerConf(engine=name, **conf)
        return Engine(container_configs)

    def __init__(self, container_configs: Dict[Text, ContainerConf]):
        self.container_configs = container_configs

    def get_config(self, container_name: Text) -> ContainerConf:
        return self.container_configs.get(container_name)
