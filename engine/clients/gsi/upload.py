from typing import List, Optional
from npy_append_array import NpyAppendArray
import numpy as np
import os
from engine.base_client.upload import BaseUploader
from engine.clients.gsi.client import GSIClient
from engine.clients.gsi.config import GSI_DEFAULT_DATA_PATH

class GSIUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, upload_params: dict):
        cls.client = GSIClient(host, connection_params)
        cls.upload_params = upload_params
        cls.connection_params = connection_params
        cls.data = None


    @classmethod
    def upload_batch(cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]):
        data = np.array(vectors)
        with NpyAppendArray(GSI_DEFAULT_DATA_PATH) as npaa:
            npaa.append(data)
            npaa.close()