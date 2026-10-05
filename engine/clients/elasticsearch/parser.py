from typing import Any

from engine.base_client.parser import BaseConditionParser, FieldValue


class ElasticConditionParser(BaseConditionParser):
    def build_condition(
        self, and_subfilters: list[Any] | None, or_subfilters: list[Any] | None
    ) -> Any | None:
        return {
            "bool": {
                "must": and_subfilters,
                "should": or_subfilters,
            }
        }

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        return {"match": {field_name: value}}

    def build_range_filter(
        self,
        field_name: str,
        lt: FieldValue | None,
        gt: FieldValue | None,
        lte: FieldValue | None,
        gte: FieldValue | None,
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
