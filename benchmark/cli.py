from enum import Enum
from typing import Optional, Text

from benchmark.backend.docker import DockerBackend
from benchmark.backend.docker.remote import DockerRemoteBackend


class BackendType(Enum):
    LOCAL = "local"
    REMOTE = "remote"


class ClientOperation(Enum):
    LOAD = "load"
    SEARCH = "search"
    CONFIGURE = "configure"


def run_backend(backend_type: BackendType, *, docker_host: Optional[Text] = None):
    """
    Create an instance of the backend based on provided type and some additional
    attributes, which are backend type specific.
    :param backend_type:
    :param docker_host:
    :return:
    """
    if BackendType.LOCAL == backend_type:
        return DockerBackend()
    if BackendType.REMOTE == backend_type:
        if docker_host is None:
            raise ValueError("The docker_host has to be provided for remote backend")
        return DockerRemoteBackend(docker_host=docker_host)
