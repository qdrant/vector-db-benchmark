import multiprocessing as mp
from typing import List, Tuple

from pymilvus import Collection, connections

from engine.base_client.search import BaseSearcher
from engine.clients.milvus.config import (
    DISTANCE_MAPPING,
    MILVUS_COLLECTION_NAME,
    MILVUS_DEFAULT_ALIAS,
    get_milvus_client,
)
from engine.clients.milvus.parser import MilvusConditionParser


class MilvusSearcher(BaseSearcher):
    search_params = {}
    client: connections = None
    collection: Collection = None
    distance: str = None
    parser = MilvusConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        cls.client = get_milvus_client(connection_params, host, MILVUS_DEFAULT_ALIAS)
        cls.collection = Collection(MILVUS_COLLECTION_NAME, using=MILVUS_DEFAULT_ALIAS)
        cls.search_params = search_params
        cls.distance = DISTANCE_MAPPING[distance]

    @classmethod
    def get_mp_start_method(cls):
        return "forkserver" if "forkserver" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        param = {"metric_type": cls.distance, "params": cls.search_params["params"]}
        try:
            res = cls.collection.search(
                data=[vector],
                anns_field="vector",
                param=param,
                limit=top,
                expr=cls.parser.parse(meta_conditions),
            )
        except Exception as e:
            import ipdb

            ipdb.set_trace()
            print("param: ", param)

            raise e

        return list(zip(res[0].ids, res[0].distances))
