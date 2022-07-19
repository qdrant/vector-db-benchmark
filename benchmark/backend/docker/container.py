import logging
from typing import Generator, Text

from benchmark.backend import Client, Container, LogsGenerator, Server
from benchmark.engine import ContainerConf, Engine

logger = logging.getLogger(__name__)


class DockerContainer(Container):

    # TODO: container should definitely know the engine it works on
    def __init__(
        self,
        engine: Engine,
        container_conf: ContainerConf,
        docker_backend: "DockerBackend",
    ):
        super().__init__(engine)
        self.container_conf = container_conf
        self._docker_backend = docker_backend
        self._docker_container = None

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

    def logs(self) -> Generator[Text, None, None]:
        for log_entry in self._docker_container.logs(stream=True, follow=True):
            yield log_entry.decode("utf-8").strip("\r\n")

    def is_ready(self) -> bool:
        # TODO: implement the healthcheck, but probably on engine level
        return True


class DockerServer(Server, DockerContainer):
    pass


class DockerClient(Client, DockerContainer):
    def configure(self, vector_size: int, distance: Text) -> LogsGenerator:
        return self.call_cmd("configure", vector_size, distance)

    def load_data(self, filename: Text, batch_size: int = 64) -> LogsGenerator:
        return self.call_cmd("load", filename, batch_size)

    def search(self, vectors_filename: Text) -> LogsGenerator:
        return self.call_cmd("search", vectors_filename)

    def call_cmd(self, cmd: Text, *args) -> LogsGenerator:
        command = f"{self.container_conf.main} {cmd} {' '.join(map(str, args))}"
        _, generator = self._docker_container.exec_run(command, stream=True)
        for entry in generator:
            entry_str = entry.decode("utf-8").strip("\r\n")
            for line in entry_str.split("\n"):
                yield line
