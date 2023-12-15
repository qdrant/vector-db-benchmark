from typing import List, Optional
import hnswlib
import os
from engine.clients.hnswlib_bench.config import DEFAULT_INDEX_PATH
from engine.base_client.upload import BaseUploader

class HNSWLibUploader(BaseUploader):
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, upload_params: dict):
        cls.upload_params = upload_params
        dim = int(os.getenv("DIM"))
        if 'gxl' in upload_params.keys():
            os.environ['GXL'] = 'true'
        else:
            os.environ['GXL'] = 'false'
        cls.index = hnswlib.Index(space=distance, dim=dim)
        cls.index.load_index(DEFAULT_INDEX_PATH)
        cls.index.resize_index(int(os.getenv("MAX_ADDS")))

    @classmethod
    def upload_batch(cls, ids: List[int], vectors: List[list], metadata: List[Optional[dict]]):
        cls.index.add_items(vectors)
        if ids[-1] == int(os.getenv("MAX_ADDS")) - 1:
            print('done uploading, saving index: shape', cls.index.get_current_count())
            cls.index.save_index(DEFAULT_INDEX_PATH)

    @classmethod
    def post_upload(cls, distance):
        print("post upload", cls.index.get_current_count())
        # cls.index.save_index(DEFAULT_INDEX_PATH)
        return {}
