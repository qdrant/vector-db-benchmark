from typing import List, Optional

from engine.base_client import IncompatibilityError
from engine.base_client.parser import BaseConditionParser, FieldValue


class LancedbConditionParser(BaseConditionParser):
    def build_condition(
        self, and_subfilters: Optional[List[str]], or_subfilters: Optional[List[str]]
    ) -> str:
        condition: str = ""
        if and_subfilters is not None:
            condition += " AND ".join(and_subfilters)

        if or_subfilters is not None:
            condition += " OR ".join(or_subfilters)
        return condition

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> str:
        return f"({field_name} = {value})"

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> str:
        out = []
        if lt:
            out.append(f"({field_name} < {lt})")
        if gt:
            out.append(f"({field_name} > {gt})")
        if lte:
            out.append(f"({field_name} <= {lte})")
        if gte:
            out.append(f"({field_name} >= {gte})")
        return "(" + " AND ".join(out) + ")"

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> str:
        raise IncompatibilityError
