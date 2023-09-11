from typing import List, Tuple
import numpy as np
import time, os

from engine.base_client.search import BaseSearcher
from engine.clients.gsi.config import GSI_DEFAULT_PORT, GSI_DEFAULT_ALLOC, GSI_DEFUALT_VERSION, GSI_DEFAULT_DATA_PATH
from engine.clients.gsi.client import GSIClient
from gsi.swagger_client.models import *


class GSISearcher(BaseSearcher):

    @classmethod
    def init_client(cls, host, connection_params: dict, search_params: dict):
        cls.search_params = search_params
        cls.client = GSIClient(host, connection_params)
        
    
    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        nbits = cls.search_params["nbits"] or 768
        search_type = cls.search_params["searchType"] or "clusters"

        # import dataset
        response = cls.client.datasets_apis.controllers_dataset_controller_import_dataset(
            ImportDatasetRequest(GSI_DEFAULT_DATA_PATH, cls.allocation_id, search_type, train_ind=True, nbits=nbits)
        )
        print("... got datasetid=", response.dataset_id)
        dataset_id = response.dataset_id
        cls.client.dataset_ids.append(dataset_id)

        # train status
        train_status = None
        while train_status != "completed":
            train_status = cls.client.dataset_apis.controllers_dataset_controller_get_train_status(
                dataset_id=dataset_id, allocation_token=cls.client.allocation_id
            ).dataset_status
            print('train status:', train_status)
            time.sleep(1)

        # write vector npy file
        tmp = np.array(vector)
        path = "/tmp/one_vec.npy"
        if os.path.exists(path):
            os.remove(path)
        np.save(path, tmp)
        # load query to fvs
        print('loading queries')
        response = cls.demo_apis.controllers_demo_controller_import_queries(
            ImportQueriesRequest(queries_file_path=path, allocation_token=cls.allocation_id)
        )
        qid, qpath = response.added_query["id"], response.added_query["queriesFilePath"]

        # load dataset
        cls.client.datasets_apis.controllers_dataset_controller_load_dataset(
            LoadDatasetRequest(allocation_id=cls.client.allocation_id, dataset_id=dataset_id),
            allocation_token=cls.client.allocation_id
        )

        # set dataset in focus
        cls.client.datasets_apis.controllers_dataset_controller_focus_dataset(
            FocusDatasetRequest(cls.client.allocation_id, dataset_id),
            cls.client.allocation_id
        )

        # search yay
        response = cls.client.search_apis.controllers_search_controller_search(
            SearchRequest(cls.client.allocation_id, dataset_id, queries_file_path=qpath, topk=top),
            cls.client.allocation_id
        )