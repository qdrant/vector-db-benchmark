from typing import Any, List, Optional

from engine.base_client.parser import BaseConditionParser, FieldValue


class PgVectorConditionParser(BaseConditionParser):
    def build_condition(
        self, and_subfilters: Optional[List[Any]], or_subfilters: Optional[List[Any]]
    ) -> Optional[Any]:
        raise NotImplementedError()

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        raise NotImplementedError()

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        raise NotImplementedError()

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        raise NotImplementedError()
