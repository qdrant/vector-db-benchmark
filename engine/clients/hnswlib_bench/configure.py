import hnswlib
import h5py
from benchmark.dataset import Dataset
import os
from engine.base_client.distances import Distance
from engine.base_client.configure import BaseConfigurator
from engine.clients.hnswlib_bench.config import DEFAULT_INDEX_PATH

class HNSWLibConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.L2: "l2",
        Distance.COSINE: "cosine",
        Distance.DOT: "ip"
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        
    def clean(self):
        os.remove(DEFAULT_INDEX_PATH)

    def recreate(self, dataset: Dataset, collection_params):
        # get index build parameters
        space = self.DISTANCE_MAPPING.get(dataset.config.distance)
        name = dataset.config.name
        datadir = "/home/jacob/vector-db-benchmark/datasets"
        f = h5py.File(f"{datadir}/{name}/{name}.hdf5")
        num_elements, dim = f['train'].shape
        print("Num Elements", num_elements, " dim", dim)
        os.environ['MAX_ADDS'] = str(num_elements)
        os.environ['DIM'] = str(dim)
        _, efc, m = collection_params['vectorIndexConfig'].values()

        # initialize and store index
        p = hnswlib.Index(space=space, dim=dim)
        p.init_index(max_elements=num_elements, ef_construction = efc, M=m)
        p.save_index(DEFAULT_INDEX_PATH)