import swagger_client as swagger_client
from swagger_client.models import *

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.clients.gsi.config import GSI_DEFAULT_PORT, GSI_DEFAULT_ALLOC, GSI_DEFUALT_VERSION
from engine.clients.gsi.client import GSIClient

class GSIConfigurator(BaseConfigurator):

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)

        self.client = GSIClient(host)

    def clean(self):
        for id in self.client.dataset_ids:
            self.client.datasets_apis.controllers_dataset_controller_remove_dataset(
                id, self.client.allocation_id
            )