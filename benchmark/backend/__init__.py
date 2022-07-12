import abc
import tempfile
from pathlib import Path
from typing import Text, Union

PathLike = Union[Text, Path]


class Container(abc.ABC):
    """
    An abstraction over a container, which is a machine running either the
    server or client of the engine.
    """

    def run(self):
        """
        Start the container using the backend
        :return:
        """
        ...

    def is_ready(self) -> bool:
        """
        A healthcheck, making sure the container is properly set up.
        :return: True, if ready to proceed, False otherwise
        """
        ...


class Server(Container, abc.ABC):
    pass


class Client(Container, abc.ABC):
    """
    An abstract client of the selected engine.
    """

    def load_data(self, filename: Text):
        """
        Loads the data with a provided filename into the selected search engine.
        This is engine-specific operation, that has the possibility to
        :param filename: a relative path from the dataset directory
        :return:
        """
        ...


class Backend:
    """
    A base class for all the possible benchmark backends.
    """

    def __init__(self, root_dir: Union[PathLike]):
        self.root_dir = root_dir if isinstance(root_dir, Path) else Path(root_dir)
        self.temp_dir = None

    def __enter__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.temp_dir.__exit__(exc_type, exc_val, exc_tb)

    def initialize_server(self, engine: Text) -> Server:
        ...

    def initialize_client(self, engine: Text) -> Client:
        ...
