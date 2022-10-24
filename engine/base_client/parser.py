from enum import Enum
from typing import Any, Dict, List, Optional, Union


class FilterType(str, Enum):
    FULL_MATCH = "match"
    RANGE = "range"
    GEO = "geo"


FieldValue = Union[str, int, float]
MetaConditions = Dict[str, List[Any]]


class BaseConditionParser:
    def parse(self, meta_conditions: Optional[MetaConditions]) -> Optional[Any]:
        """
        The parse method accepts the meta conditions stored in a dict-like
        internal benchmark structure and converts it into the representation
        used by a specific engine.

        The internal representation has the following structure:
        {
            "or": [
                {"a": {"match": {"value": 80}}},
                {"a": {"match": {"value": 2}}}
            ]
        }

        There is always an operator ("and" / "or") and a list of operands.

        :param meta_conditions:
        :return:
        """
        if meta_conditions is None or 0 == len(meta_conditions):
            return None
        return self.build_condition(
            and_subfilters=self.create_condition_subfilters(meta_conditions.get("and")),
            or_subfilters=self.create_condition_subfilters(meta_conditions.get("or")),
        )

    def build_condition(
        self, and_subfilters: Optional[List[Any]], or_subfilters: Optional[List[Any]]
    ) -> Optional[Any]:
        raise NotImplementedError

    def create_condition_subfilters(self, entries) -> Optional[List[Any]]:
        if entries is None:
            return None

        output_filters = []
        for entry in entries:
            for field_name, field_filters in entry.items():
                for condition_type, value in field_filters.items():
                    condition = self.build_filter(
                        field_name, FilterType(condition_type), value
                    )
                    output_filters.append(condition)
        return output_filters

    def build_filter(
        self, field_name: str, filter_type: FilterType, criteria: Dict[str, Any]
    ):
        if FilterType.FULL_MATCH == filter_type:
            return self.build_exact_match_filter(
                field_name, value=criteria.get("value")
            )
        if FilterType.RANGE == filter_type:
            return self.build_range_filter(
                field_name,
                lt=criteria.get("lt"),
                gt=criteria.get("gt"),
                lte=criteria.get("lte"),
                gte=criteria.get("gte"),
            )
        if FilterType.GEO == filter_type:
            return self.build_geo_filter(
                field_name,
                lon=criteria.get("lon"),
                lat=criteria.get("lat"),
                radius=criteria.get("radius"),
            )
        raise NotImplementedError

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        raise NotImplementedError

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        raise NotImplementedError

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        raise NotImplementedError
