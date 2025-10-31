from typing import Any, List, Optional

from engine.base_client.parser import BaseConditionParser, FieldValue


class QdrantNativeConditionParser(BaseConditionParser):
    """
    Parser that converts internal filter format to Qdrant REST API JSON format.
    Returns plain dictionaries instead of Pydantic models.
    """

    def build_condition(
        self, and_subfilters: Optional[List[Any]], or_subfilters: Optional[List[Any]]
    ) -> Optional[Any]:
        """Build a filter condition combining AND/OR subfilters"""
        filter_dict = {}

        if and_subfilters:
            filter_dict["must"] = and_subfilters

        if or_subfilters:
            filter_dict["should"] = or_subfilters

        return filter_dict if filter_dict else None

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        """Build an exact match filter"""
        return {
            "key": field_name,
            "match": {"value": value},
        }

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        """Build a range filter"""
        range_dict = {}
        if lt is not None:
            range_dict["lt"] = lt
        if gt is not None:
            range_dict["gt"] = gt
        if lte is not None:
            range_dict["lte"] = lte
        if gte is not None:
            range_dict["gte"] = gte

        return {
            "key": field_name,
            "range": range_dict,
        }

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        """Build a geo radius filter"""
        return {
            "key": field_name,
            "geo_radius": {
                "center": {
                    "lon": lon,
                    "lat": lat,
                },
                "radius": radius,
            },
        }
