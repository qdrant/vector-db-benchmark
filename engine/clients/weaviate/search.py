import uuid
from typing import List, Tuple

from weaviate import Client

from engine.base_client.search import BaseSearcher
from engine.clients.weaviate.config import WEAVIATE_CLASS_NAME, WEAVIATE_DEFAULT_PORT
from engine.clients.weaviate.parser import WeaviateConditionParser


class WeaviateSearcher(BaseSearcher):
    search_params = {}
    client: Client = None
    parser = WeaviateConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        url = f"http://{host}:{connection_params.pop('port', WEAVIATE_DEFAULT_PORT)}"
        cls.client = Client(url, **connection_params)
        cls.search_params = search_params

    @classmethod
    def search_one(cls, vector, meta_conditions, top) -> List[Tuple[int, float]]:
        near_vector = {"vector": vector}
        where_conditions = cls.parser.parse(meta_conditions)
        query = cls.client.query.get(
            WEAVIATE_CLASS_NAME, ["_additional {id distance}"]
        ).with_near_vector(near_vector)

        is_geo_query = False
        if where_conditions is not None:
            operands = where_conditions['operands']
            is_geo_query = any(operand['operator'] == 'WithinGeoRange' for operand in operands)
            query = query.with_where(where_conditions)

        query_obj = query.with_limit(top)
        if is_geo_query:
            # weaviate can't handle geo queries in python due to excess quotes in generated queries
            gql_query = query_obj.build()
            for field in ("geoCoordinates", "latitude", "longitude", "distance", "max"):
                gql_query = gql_query.replace(f'"{field}"', field)  # get rid of quotes
            response = cls.client.query.raw(gql_query)
        else:
            response = query_obj.do()
        res = response["data"]["Get"][WEAVIATE_CLASS_NAME]

        id_score_pairs: List[Tuple[int, float]] = []
        for obj in res:
            description = obj["_additional"]
            score = description["distance"]
            id_ = uuid.UUID(hex=description["id"]).int
            id_score_pairs.append((id_, score))
        return id_score_pairs

    def setup_search(self):
        self.client.schema.update_config(WEAVIATE_CLASS_NAME, self.search_params)


