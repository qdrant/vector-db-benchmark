import swagger_client
from swagger_client.models import *
from engine.clients.gsi.config import GSI_DEFAULT_ALLOC, GSI_DEFAULT_PORT, GSI_DEFAULT_VERSION

class GSIClient:
    def __init__(self, host, connection_params):
        config = swagger_client.Configuration()
        config.verify_ssl = False
        config.host = f"http://{host}:{GSI_DEFAULT_PORT}/{GSI_DEFAULT_VERSION}"
        api_config = swagger_client.ApiClient(config)
        api_config.default_headers["allocationToken"] = GSI_DEFAULT_ALLOC    
        self.allocation_id = GSI_DEFAULT_ALLOC

        self.datasets_apis = swagger_client.DatasetsApi(api_config)
        self.search_apis = swagger_client.SearchApi(api_config)
        self.utilities_apis = swagger_client.UtilitiesApi(api_config)
        self.boards_apis = swagger_client.BoardsApi(api_config)

        self.dataset_ids = []

    def cleanup(self):

        # print('Clearing cache...')
        # self.utilities_apis.controllers_utilities_controller_clear_cache(self.allocation_id)

        # loaded = self.boards_apis.controllers_boards_controller_get_allocations_list(self.allocation_id)
        dataset_list = self.datasets_apis.controllers_dataset_controller_get_datasets_list(self.allocation_id)
        print('Cleaning up FVS, total count:', len(dataset_list.datasets_list))
        for dataset_id in dataset_list.datasets_list:
            status = self.datasets_apis.controllers_dataset_controller_get_dataset_status(
                dataset_id=dataset_id['id'], allocation_token=self.allocation_id
            ).dataset_status
            if status == "loaded":
                self.datasets_apis.controllers_dataset_controller_unload_dataset(
                    UnloadDatasetRequest(allocation_id=self.allocation_id, dataset_id=dataset_id['id']),
                    self.allocation_id
                )
            self.datasets_apis.controllers_dataset_controller_remove_dataset(
                dataset_id=dataset_id['id'], allocation_token=self.allocation_id
            )

        print('Done cleaning')
