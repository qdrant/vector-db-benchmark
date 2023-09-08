from typing import List, Tuple
import numpy as np

from engine.base_client.search import BaseSearcher
from engine.clients.gsi.config import GSI_DEFAULT_PORT, GSI_DEFAULT_ALLOC, GSI_DEFUALT_VERSION

class GSISearcher(BaseSearcher):

    @classmethod
    def init_client(cls, host, connection_params: dict, search_params: dict):
        # initialize swagger apis
        return #TODO
    
    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        # write vector to disk as np file
        data = np.array(vector)
        np.save('/tmp/one_vec.npy', data)

        # read npy vector 
        cls.datasets