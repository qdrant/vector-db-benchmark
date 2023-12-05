from typing import List, Tuple
import numpy as np
import time, os

from engine.base_client.search import BaseSearcher
from engine.clients.gsi.config import GSI_DEFAULT_QUERY_PATH
from engine.clients.gsi.client import GSIClient
from swagger_client.models import *


class GSISearcher(BaseSearcher):

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.search_params = search_params
        cls.client = GSIClient(host, connection_params)
        print("doing search...")
    
    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        if 'ef' in cls.search_params.keys():
            ef = cls.search_params['ef']
        else:
            ef = None
            
        dataset_list = cls.client.datasets_apis.controllers_dataset_controller_get_datasets_list(
            cls.client.allocation_id
            ).datasets_list
        dataset_id = dataset_list[-1]['id']


        response = cls.client.search_apis.controllers_search_controller_search(
            SearchRequest(allocation_id=cls.client.allocation_id, dataset_id=dataset_id, 
                          queries_file_path=GSI_DEFAULT_QUERY_PATH, topk=top, ef_search=ef),
            cls.client.allocation_id
        )
        # parse results
        # print('parse results')
        inds, dists = response.indices, response.distance
        id_score_pairs: List[Tuple[int, float]] = []
        for ind, dist in zip(inds[0], dists[0]):
            id_score_pairs.append((ind, dist))

        # cls.client.cleanup()
        return id_score_pairs
