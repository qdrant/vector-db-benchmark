from typing import Any, List, Optional

from engine.base_client.parser import BaseConditionParser, FieldValue


class ClickHouseConditionParser(BaseConditionParser):
    """
    The internal representation has the following structure:
        {
            "or": [
                {"a": {"match": {"value": 80}}},
                {"a": {"match": {"value": 2}}}
            ]
        }
    """

    def build_condition(
            self, and_subfilters: Optional[List[Any]], or_subfilters: Optional[List[Any]]
    ) -> Optional[Any]:
        clauses = []
        if or_subfilters is not None and len(or_subfilters) > 0:
            clauses.append("(" + " OR ".join(self._build_clauses(or_subfilters)) + ")")
        if and_subfilters is not None and len(and_subfilters) > 0:
            clauses.append("(" + " AND ".join(self._build_clauses(and_subfilters)) + ")")
        if len(clauses) > 0:
            return " AND ".join(clauses)
        return "1=1"

    def _build_clauses(self, filters):
        clauses = []
        for filter in filters:
            for column, value in filter.items():
                # we may need to evaluate types here to determine if quotes needed
                clauses.append(f"{column} = '{value['match']['value']}'")
        return clauses

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        return f"{field_name} = '{value}'"

    def build_range_filter(
            self,
            field_name: str,
            lt: Optional[FieldValue],
            gt: Optional[FieldValue],
            lte: Optional[FieldValue],
            gte: Optional[FieldValue],
    ) -> Any:
        return f"{field_name} < {lt} AND {field_name} > {gt} AND {field_name} >= {gte} AND {field_name} <= {lte}"

    def build_geo_filter(
            self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        return f"geo_distance(lon, lat, {lon}, {lat})"
