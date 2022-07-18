import abc
import tempfile
from pathlib import Path
from typing import Text, Union, Generator, Optional

from benchmark.engine import Engine
from benchmark.types import PathLike

LogsGenerator = Generator[Text, None, None]


class Container(abc.ABC):
    """
    An abstraction over a container, which is a machine running either the
    server or client of the engine.
    """

    def __init__(self, engine: Engine):
        self.engine = engine
        self.volumes = []

    def mount(self, source: PathLike, target: PathLike):
        """
        Add provided source root_dir as a target in the container to be mounted
        when .run method is called.
        :param source:
        :param target:
        :return:
        """
        self.volumes.append(f"{source}:{target}")

    def run(self):
        """
        Start the container using the backend
        :return:
        """
        ...

    def remove(self):
        """
        Stop and remove the container using backend
        :return:
        """
        ...

    def logs(self) -> Generator[Text, None, None]:
        """
        Iterate through all the logs produced by the container
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

    def configure(self, vector_size: int, distance: Text) -> LogsGenerator:
        """
        Set up the engine before any data is being loaded. Should be executed
        once before any client loads it data.
        :param vector_size:
        :param distance:
        :return:
        """
        ...

    def load_data(self, filename: Text, batch_size: int = 64) -> LogsGenerator:
        """
        Load the data with a provided filename into the selected search engine.
        This is engine-specific operation, that has the possibility to
        :param filename: a relative root_dir from the dataset directory
        :param batch_size: number of vectors to store with a single call
        :return:
        """
        ...

    def search(self, vectors_filename: Text) -> LogsGenerator:
        """
        Perform the search operation with vectors coming from the provided file.
        :param vectors_filename:
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

    def initialize_server(self, engine: Engine) -> Server:
        ...

    def initialize_client(self, engine: Engine) -> Client:
        ...
