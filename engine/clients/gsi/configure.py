import swagger_client
from swagger_client.models import *

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.clients.gsi.config import GSI_DEFAULT_PORT, GSI_DEFAULT_ALLOC, GSI_DEFUALT_VERSION

class GSIConfigurator(BaseConfigurator):

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)

        config = swagger_client.Configuration()
        config.verify_ssl = False
        config.host = f"http://{host}:{connection_params.pop('port', GSI_DEFAULT_PORT)}/{GSI_DEFUALT_VERSION}"


        api_config = swagger_client.ApiClient(config)
        api_config.default_headers["allocationToken"] = GSI_DEFAULT_ALLOC
        self.allocation_id = GSI_DEFAULT_ALLOC

        self.datasets_apis = swagger_client.DatasetsApi(api_config)
        self.dataset_apis = swagger_client.DatasetApi(api_config)
        self.search_apis = swagger_client.SearchApi(api_config)
        self.utilities_apis = swagger_client.UtilitiesApi(api_config)
        self.demo_apis = swagger_client.DemoApi(api_config)

        self.dataset_ids = []

    def clean(self):
        for id in self.dataset_ids:
            self.datasets_apis.controllers_dataset_controller_remove_dataset(id, self.allocation_id)
        
    
    def recreate(self, dataset: Dataset, collection_params):

        return # TODO