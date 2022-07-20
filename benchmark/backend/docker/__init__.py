import logging
from typing import List, Optional, Text, Union

import docker
import docker.errors

from benchmark import BASE_DIRECTORY
from benchmark.backend import Backend, Client, Server
from benchmark.backend.docker.container import (
    DockerClient,
    DockerContainer,
    DockerServer,
)
from benchmark.engine import Engine
from benchmark.types import PathLike

logger = logging.getLogger(__name__)


class DockerBackend(Backend):
    """
    A Docker based backend for the benchmarks, using separate containers for
    server and client/s.
    """

    NETWORK_NAME = "vector-benchmark"

    def __init__(
        self,
        root_dir: Union[PathLike] = BASE_DIRECTORY,
        docker_client: Optional[docker.DockerClient] = None,
    ):
        super().__init__(root_dir)
        if docker_client is None:
            docker_client = docker.from_env()
        self.docker_client = docker_client
        self.containers: List[DockerContainer] = []

    def __enter__(self):
        super().__enter__()
        # Get or create a network, as this may exist already after some failed
        # attempts to run the tests
        try:
            self.network = self.docker_client.networks.get(self.NETWORK_NAME)
        except docker.errors.NotFound:
            self.network = self.docker_client.networks.create(self.NETWORK_NAME)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)

        # Kill all the containers on the context manager exit, so there are no
        # orphaned containers once the benchmark is finished
        for container in self.containers:
            container.remove()

        # Finally get rid of the network as well
        try:
            self.network.remove()
        except docker.errors.APIError:
            logger.debug("The network could not be removed", exc_info=True)

    def initialize_server(self, engine: Engine, container: Text = "server") -> Server:
        server_conf = engine.get_config(container)
        logger.info("Initializing server: %s", server_conf)
        server = DockerServer(engine, server_conf, self)
        self.containers.append(server)
        return server

    def initialize_client(self, engine: Engine, container: Text = "client") -> Client:
        client_conf = engine.get_config(container)
        logger.info("Initializing client: %s", client_conf)
        client = DockerClient(engine, client_conf, self)
        self.containers.append(client)
        return client
