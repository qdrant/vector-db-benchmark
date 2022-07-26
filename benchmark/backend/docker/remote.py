import logging
from typing import Text, Tuple

import docker
import docker.errors
import docker.models.images
import docker.models.volumes

from benchmark.backend.docker import DockerBackend
from benchmark.backend.docker.container import DockerClient, DockerContainer
from benchmark.dataset import Dataset
from benchmark.engine import ContainerConf

logger = logging.getLogger(__name__)


class DockerRemoteBackend(DockerBackend):
    """
    A remote version of the backend using Docker to run the containers. It
    connects to the provided Docker daemon and runs all the commands remotely.
    A big difference comparing to the local Docker backend is a need to expose
    the server ports to public, so all the clients may communicate with it.
    """

    def __init__(self, docker_host: Text):
        docker_client = docker.DockerClient(base_url=docker_host)
        super().__init__(docker_client)
        self.local_docker_client = docker.from_env()

    def initialize_dataset(self, dataset: Dataset):
        # Created volume should be mounted to the clients
        volume = self._create_volume(dataset.name)
        self.dataset_volume = volume.name

        # Build the Docker image locally
        logger.info("Building the %s dataset container locally", dataset.name)
        image = self._build_local_image(dataset)

        # Push the local image to the remote Docker
        logger.info("Pushing the local %s image to remote Docker", image.id)
        remote_image = self._push_image_to_remote(image)
        logger.info(
            "Local image %s loaded as remote image %s", image, remote_image
        )

        # Finally, the temporary dataset container might be created and launched
        # to load the data to be then used by clients
        container_conf = ContainerConf(image=remote_image.id)
        container = DockerContainer(container_conf, self)
        container.mount(self.dataset_volume, "/dataset")
        container.run()

    def _create_volume(self, name: Text) -> docker.models.volumes.Volume:
        """
        Create a docker volume if it doesn't exist already. Created volume will
        have the same name as the
        :param name:
        :return:
        """
        try:
            # If the volume already exists, then we don't need to create it
            # again, as there is a different container using the same dataset
            volume = self.docker_client.volumes.get(name)
            logger.info("Omitting %s volume creation as it already exists", name)
            return volume
        except docker.errors.NotFound:
            logger.info("Could not find a volume named %s. Creating new", name)
            return self.docker_client.volumes.create(name)

    def _build_local_image(self, dataset: Dataset) -> docker.models.images.Image:
        """
        Build the dataset image locally and return its internal Docker
        representation
        :param dataset:
        :return:
        """
        container_conf = ContainerConf(
            dataset=dataset.name,
            dockerfile="Dockerfile",
        )
        image, _ = self.local_docker_client.images.build(
            tag=f"vector-db-benchmark-{dataset.name}",
            path=str(container_conf.dockerfile_path()),
            dockerfile=container_conf.dockerfile,
        )
        return image

    def _push_image_to_remote(
        self, image: docker.models.images.Image
    ) -> docker.models.images.Image:
        """
        Push local image to remote host, so it can be launched there.
        :param image: internal Docker image binary representation
        :return: the same image, but on a remote host
        """
        images = self.docker_client.images.load(image.save())
        return images[0]
