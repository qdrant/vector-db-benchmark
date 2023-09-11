from typing import List, Tuple
import numpy as np
import time
import gsi.swagger_client as swagger_client
from gsi.swagger_client.models import *

from engine.base_client.search import BaseSearcher
from engine.clients.gsi.config import GSI_DEFAULT_PORT, GSI_DEFAULT_ALLOC, GSI_DEFUALT_VERSION


class GSISearcher(BaseSearcher):

    @classmethod
    def init_client(cls, host, connection_params: dict, search_params: dict):
        cls.search_params = search_params

        config = swagger_client.Configuration()
        config.verify_ssl = False
        config.host = f"http://{host}:{connection_params.pop('port', GSI_DEFAULT_PORT)}/{GSI_DEFUALT_VERSION}"

        api_config = swagger_client.ApiClient(config)
        api_config.default_headers["allocationToken"] = GSI_DEFAULT_ALLOC
        cls.allocation_id = GSI_DEFAULT_ALLOC

        cls.datasets_apis = swagger_client.DatasetsApi(api_config)
        cls.dataset_apis = swagger_client.DatasetApi(api_config)
        cls.search_apis = swagger_client.SearchApi(api_config)
        cls.utilities_apis = swagger_client.UtilitiesApi(api_config)
        cls.demo_apis = swagger_client.DemoApi(api_config)
        
    
    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        nbits = cls.search_params["nbits"]
        search_type = cls.search_params["searchType"]

        # write vector to disk as npy file
        tmp = np.array(vector)
        path = "/tmp/one_vec.npy"
        np.save(path, tmp)

        response = cls.demo_apis.controllers_demo_controller_import_queries(
            ImportQueriesRequest(queries_file_path=path, allocation_token=cls.allocation_id)
        )
        qid, qpath = response.added_query["id"], response.added_query["queriesFilePath"]
        # TODO: get dataset ID for focus
        # TODO: run query, unfocus dataset, remove query and tmp file