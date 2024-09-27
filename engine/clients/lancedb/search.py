from typing import List, Tuple

import lancedb
from lancedb import DBConnection
from lancedb.query import LanceVectorQueryBuilder

from dataset_reader.base_reader import Query
from engine.base_client.search import BaseSearcher
from engine.clients.lancedb import LancedbConfigurator
from engine.clients.lancedb.config import LANCEDB_COLLECTION_NAME
from engine.clients.lancedb.parser import LancedbConditionParser


class LancedbSearcher(BaseSearcher):
    client: DBConnection = None
    parser = LancedbConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        uri = "~/.lancedb"
        cls.client = lancedb.connect(uri, **connection_params)
        cls.distance = distance

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        tbl = cls.client.open_table(name=LANCEDB_COLLECTION_NAME)
        df: LanceVectorQueryBuilder = tbl.search(query.vector)
        results = (
            df.metric(LancedbConfigurator.DISTANCE_MAPPING.get(cls.distance))
            .where(cls.parser.parse(query.meta_conditions), prefilter=True)
            .select(["id"])
            .limit(top)
            .to_list()
        )

        return [(result["id"], result["_distance"]) for result in results]
