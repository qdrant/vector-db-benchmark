from typing import Any, List, Optional, Text

from engine.base_client.parser import BaseConditionParser, FieldValue


class ElasticConditionParser(BaseConditionParser):
    def build_condition(
        self, and_statements: List[Any], or_statements: List[Any]
    ) -> Optional[Any]:
        return {
            "query": {
                "bool": {
                    "must": and_statements,
                    "should": or_statements,
                }
            }
        }

    def build_exact_match_filter(self, field_name: Text, value: FieldValue) -> Any:
        return {"match": {field_name: value}}

    def build_range_filter(
        self,
        field_name: Text,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        return {"range": {"lt": lt, "gt": gt, "lte": lte, "gte": gte}}

    def build_geo_filter(
        self, field_name: Text, lat: float, lon: float, radius: float
    ) -> Any:
        return {
            "geo_distance": {
                "distance": f"{radius}m",
                field_name: {"lat": lat, "lon": lon},
            }
        }
