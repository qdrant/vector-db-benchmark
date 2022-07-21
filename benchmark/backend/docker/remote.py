from typing import Text

import docker

from benchmark.backend.docker import DockerBackend


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
