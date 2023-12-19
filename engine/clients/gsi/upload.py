from typing import List, Optional
from npy_append_array import NpyAppendArray
import numpy as np
import h5py
import os, time
from swagger_client.models import *
from engine.base_client.upload import BaseUploader
from engine.clients.gsi.client import GSIClient
from engine.clients.gsi.config import *

class GSIUploader(BaseUploader):
    client = None
    global skip
    skip = True

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, upload_params: dict):
        cls.client = GSIClient(host, connection_params)
        cls.upload_params = upload_params
        print("upload params:", upload_params)
        cls.connection_params = connection_params
        cls.data = None

        if os.path.exists(GSI_DEFAULT_DATA_PATH):
            os.remove(GSI_DEFAULT_DATA_PATH)

        # get dataset shape
        path = os.path.join(os.path.abspath("./datasets"), os.getenv("DATA_PATH"))
        if os.getenv("dataset") == "laion-small-clip":
            path = os.path.join(path, "vectors.npy")
            train = np.load(path)
            cls.shape = train.shape[0]
        else:
            file = h5py.File(path)
            train = file['train'][:]
            cls.shape = file['train'].shape[0]
            
        print(f"saving {path} to {GSI_DEFAULT_DATA_PATH}")
        np.save(GSI_DEFAULT_DATA_PATH, train)
        cls.fvs_upload()

    @classmethod
    def upload_batch(cls, ids: List[int], vectors: List[list], metadata: Optional[List[dict]]):
        return

    @classmethod
    def fvs_upload(cls):
        nbits = cls.upload_params["nbits"] or 768
        search_type = cls.upload_params["searchType"] or "flat"
        top = cls.upload_params["top"] or 10
        m, efc = None, None
        if search_type == "hnsw":
            m = cls.upload_params["m"] or None
            efc = cls.upload_params["efConstruction"] or None

        # convert dataset to float32...
        data = np.load(GSI_DEFAULT_DATA_PATH)
        if not isinstance(np.float32, type(data[0][0])):
            data = np.float32(data)
        if os.path.exists(GSI_DEFAULT_DATA_PATH):
            os.remove(GSI_DEFAULT_DATA_PATH)
        np.save(GSI_DEFAULT_DATA_PATH, data)

        # import dataset
        response = cls.client.datasets_apis.controllers_dataset_controller_import_dataset(
            ImportDatasetRequest(records=GSI_DEFAULT_DATA_PATH, search_type=search_type, train_ind=True,
                                 nbits=nbits, dataset_name="QdrantBench", m_number_of_edges=m, ef_construction=efc,
                                 num_of_boards=cls.upload_params["num_of_boards"], num_of_clusters=cls.upload_params["num_of_clusters"]),
            cls.client.allocation_id
        )
        print("got datasetid=", response.dataset_id)
        dataset_id = response.dataset_id
        cls.client.dataset_ids.append(dataset_id)

        # train status
        train_status = cls.client.datasets_apis.controllers_dataset_controller_get_dataset_status(
                dataset_id=dataset_id, allocation_token=cls.client.allocation_id
            ).dataset_status
        print("training, status currently:", train_status)
        while train_status != "completed":
            train_status = cls.client.datasets_apis.controllers_dataset_controller_get_dataset_status(
                dataset_id=dataset_id, allocation_token=cls.client.allocation_id
            ).dataset_status
            time.sleep(10)

        # load dataset
        print('done training, loading dataset...')

        load_status = cls.client.datasets_apis.controllers_dataset_controller_load_dataset(
                LoadDatasetRequest(allocation_id=cls.client.allocation_id, dataset_id=dataset_id, topk=top,
                                   centroids_hamming_k=cls.upload_params["centroids_hamming_k"],
                                   centroids_rerank=cls.upload_params["centroid_rerank"], hamming_k=cls.upload_params["hamming_k"],
                                   ),
                allocation_token=cls.client.allocation_id
            ).status
        
        print(load_status)

        # set dataset in focus
        print('focus dataset')
        cls.client.datasets_apis.controllers_dataset_controller_focus_dataset(
            FocusDatasetRequest(cls.client.allocation_id, dataset_id),
            cls.client.allocation_id
        )