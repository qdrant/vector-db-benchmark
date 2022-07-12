import json
from dataclasses import dataclass
from pathlib import Path
from typing import Text, Union, Optional, Dict, List

from benchmark.backend import Backend, PathLike, Server, Client, Container
from docker.models import containers

import logging
import docker


logger = logging.getLogger(__name__)


@dataclass
class DockerContainerConf:
    engine: Text
    image: Optional[Text] = None
    dockerfile: Optional[Text] = None
    environment: Optional[Dict[Text, Union[Text, int, bool]]] = None
    main: Optional[Text] = None
    hostname: Optional[Text] = None

    @classmethod
    def from_file(
        cls, path: Text, engine: Text, container: Text = "server"
    ) -> "DockerContainerConf":
        with open(path, "r") as fp:
            conf = json.load(fp)
            return DockerContainerConf(engine=engine, **conf[container])

    def dockerfile_path(self, root_dir: Path) -> Path:
        """
        Calculates the absolute path to the directory containing the dockerfile,
        using given root directory as a base.
        :param root_dir:
        :return:
        """
        return root_dir / "engine" / self.engine


class DockerContainer(Container):
    def __init__(
        self,
        container_conf: DockerContainerConf,
        docker_backend: "DockerBackend",
    ):
        self.container_conf = container_conf
        self.docker_backend = docker_backend
        self.container: containers.Container = None
        self.volumes = []

    def mount(self, source: PathLike, target: PathLike):
        self.volumes.append(f"{source}:{target}")

    def run(self):
        # Build the dockerfile if it was provided as a container image. This is
        # typically done for the clients, as they may require some custom setup
        if self.container_conf.dockerfile is not None:
            dockerfile_path = self.container_conf.dockerfile_path(
                self.docker_backend.root_dir
            )
            image, logs = self.docker_backend.docker_client.images.build(
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
        self.container = self.docker_backend.docker_client.containers.run(
            self.container_conf.image,
            detach=True,
            volumes=self.volumes,
            environment=self.container_conf.environment,
            hostname=self.container_conf.hostname,
            network=self.docker_backend.network.name,
        )

        # TODO: remove the image on exit

    def logs(self):
        for log_entry in self.container.logs(stream=True, follow=True):
            yield log_entry

    def is_ready(self) -> bool:
        # TODO: implement the healthcheck
        return True


class DockerServer(Server, DockerContainer):
    pass


class DockerClient(Client, DockerContainer):
    def load_data(self, filename: Text):
        command = f"{self.container_conf.main} load {filename}"
        _, generator = self.container.exec_run(command, stream=True)
        return generator


class DockerBackend(Backend):
    """
    A Docker based backend for the benchmarks, using separate containers for
    server and client/s.
    """

    NETWORK_NAME = "vector-benchmark"

    def __init__(
        self,
        root_dir: Union[PathLike],
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
            container.container.kill()

        # Remove the data volume as well, so there won't be any volume left
        # self.data_volume.remove()

        # Finally get rid of the network as well
        self.network.remove()

    def initialize_server(self, engine: Text) -> Server:
        server_conf = DockerContainerConf.from_file(
            self.root_dir / "engine" / engine / "config.json",
            engine=engine,
            container="server",
        )
        logger.info("Initializing %s server: %s", engine, server_conf)
        server = DockerServer(server_conf, self)
        self.containers.append(server)
        return server

    def initialize_client(self, engine: Text) -> Client:
        # TODO: Create a docker volume so the data is available on client instances
        client_conf = DockerContainerConf.from_file(
            self.root_dir / "engine" / engine / "config.json",
            engine=engine,
            container="client",
        )
        logger.info("Initializing %s client: %s", engine, client_conf)
        client = DockerClient(client_conf, self)
        self.containers.append(client)
        return client
