import logging
from typing import Generator, List, Optional, Text, Union

import docker
from docker.models import containers

from benchmark import BASE_DIRECTORY
from benchmark.backend import Backend, Client, Container, Server
from benchmark.engine import ContainerConf, Engine
from benchmark.types import PathLike

logger = logging.getLogger(__name__)


class DockerContainer(Container):
    def __init__(
        self,
        container_conf: ContainerConf,
        docker_backend: "DockerBackend",
    ):
        super().__init__()
        self.container_conf = container_conf
        self._docker_backend = docker_backend
        self._docker_container: containers.Container = None

    def run(self):
        # Build the dockerfile if it was provided as a container image. This is
        # typically done for the clients, as they may require some custom setup
        if self.container_conf.dockerfile is not None:
            dockerfile_path = self.container_conf.dockerfile_path(
                self._docker_backend.root_dir
            )
            image, logs = self._docker_backend.docker_client.images.build(
                path=str(dockerfile_path),
                dockerfile=self.container_conf.dockerfile,
            )
            self.container_conf.image = image.id
            logger.info(
                "Built %s into a Docker image %s",
                self.container_conf.dockerfile,
                image.id,
            )

        # Create the container either using the image or dockerfile, if that was
        # provided. The dockerfile has a preference over the image name.
        logger.debug("Running a container using image %s", self.container_conf.image)
        self._docker_container = self._docker_backend.docker_client.containers.run(
            self.container_conf.image,
            detach=True,
            volumes=self.volumes,
            environment=self.container_conf.environment,
            hostname=self.container_conf.hostname,
            network=self._docker_backend.network.name,
        )

        # TODO: remove the image on exit

    def remove(self):
        # Sometimes the container has been created but not launched, so the
        # underlying Docker container won't be created
        if self._docker_container is not None:
            self._docker_container.stop()
            self._docker_container.remove()

    def logs(self) -> Generator[Union[Text, bytes], None, None]:
        for log_entry in self._docker_container.logs(stream=True, follow=True):
            yield log_entry

    def is_ready(self) -> bool:
        # TODO: implement the healthcheck, but probably on engine level
        return True


class DockerServer(Server, DockerContainer):
    pass


class DockerClient(Client, DockerContainer):
    def load_data(self, filename: Text):
        command = f"{self.container_conf.main} load {filename}"
        _, generator = self._docker_container.exec_run(command, stream=True)
        return generator


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
        self.network = self.docker_client.networks.create(self.NETWORK_NAME)
        # self.data_volume = self.docker_client.volumes.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)

        # Kill all the containers on the context manager exit, so there are no
        # orphaned containers once the benchmark is finished
        for container in self.containers:
            container.remove()

        # Finally get rid of the network as well
        self.network.remove()

    def initialize_server(self, engine: Engine) -> Server:
        server_conf = engine.get_config("server")
        logger.info("Initializing %s server: %s", engine, server_conf)
        server = DockerServer(server_conf, self)
        self.containers.append(server)
        return server

    def initialize_client(self, engine: Engine) -> Client:
        client_conf = engine.get_config("client")
        logger.info("Initializing %s client: %s", engine, client_conf)
        client = DockerClient(client_conf, self)
        self.containers.append(client)
        return client
