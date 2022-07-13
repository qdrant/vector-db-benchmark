from pathlib import Path
from typing import Text

from benchmark import BASE_DIRECTORY


class Dataset:

    @classmethod
    def from_name(cls, name: Text) -> "Dataset":
        # TODO: load dataset info from given path
        return Dataset(name)

    def __init__(self, name: Text):
        self.name = name

    def path(self) -> Path:
        return BASE_DIRECTORY / "dataset" / self.name
