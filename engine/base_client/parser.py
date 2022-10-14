from enum import Enum
from typing import Any, Dict, List, Optional, Text, Union


class FilterType(str, Enum):
    FULL_MATCH = "match"
    RANGE = "range"
    GEO = "geo"

    @classmethod
    def from_value(cls, value: Text) -> "FilterType":
        for allowed_value in FilterType:
            if allowed_value == value:
                return allowed_value
        raise ValueError("Requested non-supported enum member")


FieldValue = Union[Text, int, float]


class BaseConditionParser:
    def parse(self, meta_conditions: Dict[Text, Any]) -> Optional[Any]:
        if meta_conditions is None or 0 == len(meta_conditions):
            return None
        return self.build_condition(
            and_statements=self.create_filter_part(meta_conditions.get("and")),
            or_statements=self.create_filter_part(meta_conditions.get("or")),
        )

    def build_condition(
        self, and_statements: List[Any], or_statements: List[Any]
    ) -> Optional[Any]:
        raise NotImplementedError

    def create_filter_part(self, entries) -> Optional[List[Any]]:
        if entries is None:
            return None

        output_filters = []
        for entry in entries:
            for field_name, field_filters in entry.items():
                for condition_type, value in field_filters.items():
                    condition = self.build_filter(
                        field_name, FilterType.from_value(condition_type), value
                    )
                    output_filters.append(condition)
        return output_filters

    def build_filter(
        self, field_name: Text, filter_type: FilterType, criteria: Dict[Text, Any]
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

    def build_exact_match_filter(self, field_name: Text, value: FieldValue) -> Any:
        raise NotImplementedError

    def build_range_filter(
        self,
        field_name: Text,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        raise NotImplementedError

    def build_geo_filter(
        self, field_name: Text, lat: float, lon: float, radius: float
    ) -> Any:
        raise NotImplementedError
