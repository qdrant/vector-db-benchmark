from engine.base_client.configure import BaseConfigurator
from engine.clients.gsi.client import GSIClient
from benchmark.dataset import Dataset

class GSIConfigurator(BaseConfigurator):

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)

        self.client = GSIClient(host, connection_params)

    def clean(self):
        self.client.cleanup()

    def recreate(self, dataset: Dataset, collection_params):
        pass