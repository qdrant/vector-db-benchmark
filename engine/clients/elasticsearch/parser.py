from typing import Any, List, Optional

from engine.base_client.parser import BaseConditionParser, FieldValue


class ElasticConditionParser(BaseConditionParser):
    def build_condition(
        self, and_subfilters: Optional[List[Any]], or_subfilters: Optional[List[Any]]
    ) -> Optional[Any]:
        bool_clause = {}
        if and_subfilters:
            bool_clause["must"] = and_subfilters
        if or_subfilters:
            bool_clause["should"] = or_subfilters
        if not bool_clause:
            return None
        return {"bool": bool_clause}

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        return {"match": {field_name: value}}

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        return {"range": {field_name: {"lt": lt, "gt": gt, "lte": lte, "gte": gte}}}

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        return {
            "geo_distance": {
                "distance": f"{radius}m",
                field_name: {"lat": lat, "lon": lon},
            }
        }
