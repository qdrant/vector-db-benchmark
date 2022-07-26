import abc
import logging
import tempfile
from pathlib import Path
from typing import Generator, Optional, Text, Union

from benchmark.dataset import Dataset
from benchmark.engine import Engine, EnvironmentalVariables
from benchmark.types import PathLike

LogsGenerator = Generator[Text, None, None]

logger = logging.getLogger(__name__)


class Container(abc.ABC):
    """
    An abstraction over a container, which is a machine running either the
    server or client of the engine.
    """

    def __init__(self):
        self.volumes = []

    def mount(self, source: PathLike, target: PathLike):
        """
        Add provided source root_dir as a target in the container to be mounted
        when .run method is called.
        :param source:
        :param target:
        :return:
        """
        logger.info("Mounting host %s to guest %s", source, target)
        self.volumes.append(f"{source}:{target}")

    def run(self, environment: Optional[EnvironmentalVariables] = None):
        """
        Start the container using the backend. If
        :type environment: dictionary containing the environmental variables
                           that will be provided to the container
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

    def configure(
        self, collection_name, ef_construction, max_connections, distance, vector_size
    ) -> LogsGenerator:
        """
        Set up the engine before any data is being loaded. Should be executed
        once before any client loads it data.
        """
        ...

    def load_data(
        self, collection_name, filename, batch_size, parallel
    ) -> LogsGenerator:
        """
        Load the data with a provided filename into the selected search engine.
        This is engine-specific operation, that has the possibility to
        """
        ...

    def search(self, collection_name, filename, ef, parallel) -> LogsGenerator:
        """
        Perform the search operation with vectors coming from the provided file.
        """
        ...


class Backend:
    """
    A base class for all the possible benchmark backends.
    """

    def __init__(self):
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

    def initialize_dataset(self, dataset: Dataset):
        ...
