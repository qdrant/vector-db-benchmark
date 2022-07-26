import os
import logging
from typing import List, Optional, Text


import docker
import docker.errors

from benchmark.backend import Backend, Client, Server
from benchmark.backend.docker.container import (
    DockerClient,
    DockerContainer,
    DockerServer,
)
from benchmark.dataset import Dataset
from benchmark import BASE_DIRECTORY
from benchmark.engine import ContainerConf, Engine

logger = logging.getLogger(__name__)


class DockerBackend(Backend):
    """
    A Docker based backend for the benchmarks, using separate containers for
    server and client/s. This version used a local Docker daemon for running
    all the containers.
    """

    NETWORK_NAME = "vector-benchmark"

    def __init__(
        self,
        docker_client: Optional[docker.DockerClient] = None,
    ):
        super().__init__()
        if docker_client is None:
            docker_client = docker.from_env()
        self.docker_client = docker_client
        self.containers: List[DockerContainer] = []
        self.dataset_volume = None

    def __enter__(self):
        super().__enter__()
        self.network = self._create_network()
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
        logger.info("Initializing %s server: %s", engine, server_conf)
        server = DockerServer(server_conf, self)
        self.containers.append(server)
        return server

    def initialize_client(self, engine: Engine, container: Text = "client") -> Client:
        if self.dataset_volume is None:
            raise ValueError(
                "Dataset has not been initialized. Did you launch "
                "initialize_dataset before?"
            )

        client_conf = engine.get_config(container)
        logger.info("Initializing %s client: %s", engine, client_conf)
        client = DockerClient(client_conf, self)
        client.mount(self.dataset_volume, "/dataset")
        self.containers.append(client)
        return client

    def initialize_dataset(self, dataset: Dataset):
        # Dataset might be downloaded using a temporary container, so it
        # is available on all the client containers after
        logger.info("Downloading the dataset %s", dataset.name)
        container_conf = ContainerConf(
            dataset=dataset.name,
            dockerfile="Dockerfile",
        )
        client = DockerClient(container_conf, self)
        client.mount(dataset.root_dir, "/dataset")
        client.run()

        # The dataset will be mounted from the local filesystem
        self.dataset_volume = dataset.root_dir

    def _create_network(self):
        """
        Get or create a network, as this may exist already after some failed
        attempts to run the tests.
        :return:
        """
        try:
            return self.docker_client.networks.get(self.NETWORK_NAME)
        except docker.errors.NotFound:
            return self.docker_client.networks.create(self.NETWORK_NAME)

    def build_from_dockerfile(self, conf: ContainerConf):
        if conf.dataset:
            image, logs = self.docker_client.images.build(
                path=str(conf.dockerfile_path()),
                dockerfile=conf.dockerfile,
            )
        else:
            image, logs = self.docker_client.images.build(
                path=str(BASE_DIRECTORY / "engine"),
                dockerfile=os.path.join(conf.engine, conf.dockerfile),
            )
        logger.info(
            "Built %s into a Docker image %s",
            conf.dockerfile,
            image.id,
        )
        return image
