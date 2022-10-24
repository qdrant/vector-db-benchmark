from typing import Any, Dict, List, Optional, Text

from engine.base_client import IncompatibilityError
from engine.base_client.parser import BaseConditionParser, FieldValue


class WeaviateConditionParser(BaseConditionParser):
    def parse(self, meta_conditions: Dict[Text, Any]) -> Optional[Any]:
        if meta_conditions is None or len(meta_conditions) == 0:
            return {}
        return super().parse(meta_conditions)

    def build_condition(
        self, and_subfilters: Optional[List[Any]], or_subfilters: Optional[List[Any]]
    ) -> Optional[Any]:
        clause = {}
        if or_subfilters is not None and len(or_subfilters) > 0:
            clause = {
                "operator": "Or",
                "operands": or_subfilters,
            }
        if and_subfilters is not None and len(and_subfilters) > 0:
            clause = {
                "operator": "And",
                "operands": and_subfilters + [clause]
                if len(clause) > 0
                else and_subfilters,
            }
        return clause

    def build_exact_match_filter(self, field_name: Text, value: FieldValue) -> Any:
        return {
            "operator": "Equal",
            "path": [field_name],
            self.value_key(value): value,
        }

    def build_range_filter(
        self,
        field_name: Text,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        clauses = {
            "LessThan": lt,
            "GreaterThan": gt,
            "LessThanEqual": lte,
            "GreaterThanEqual": gte,
        }
        return {
            "operator": "And",
            "operands": [
                {
                    "operator": op,
                    "path": [field_name],
                    self.value_key(value): value,
                }
                for op, value in clauses.items()
                if value is not None
            ],
        }

    def build_geo_filter(
        self, field_name: Text, lat: float, lon: float, radius: float
    ) -> Any:
        return {
            "operator": "WithinGeoRange",
            "path": [field_name],
            "valueGeoRange": {
                "geoCoordinates": {
                    "latitude": lat,
                    "longitude": lon,
                },
                "distance": {"max": radius},
            },
        }

    def value_key(self, value: FieldValue) -> Text:
        if isinstance(value, Text):
            return "valueString"
        if isinstance(value, int):
            return "valueInt"
        if isinstance(value, float):
            return "valueNumber"
        raise IncompatibilityError
