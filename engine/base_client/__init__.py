from engine.base_client.client import BaseClient
from engine.base_client.configure import BaseConfigurator
from engine.base_client.search import BaseSearcher
from engine.base_client.upload import BaseUploader


class IncompatibilityError(Exception):
    pass


__all__ = [
    "BaseClient",
    "BaseConfigurator",
    "BaseSearcher",
    "BaseUploader",
    "IncompatibilityError",
]
