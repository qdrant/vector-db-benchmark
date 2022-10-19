import json
from typing import Any, List, Optional, Text

from engine.base_client import IncompatibilityError
from engine.base_client.parser import BaseConditionParser, FieldValue


class MilvusConditionParser(BaseConditionParser):
    def build_condition(
        self, and_statements: List[Any], or_statements: List[Any]
    ) -> Optional[Any]:
        clauses = []
        if or_statements is not None and len(or_statements) > 0:
            clauses.append("(" + " || ".join(or_statements) + ")")
        if and_statements is not None and len(and_statements) > 0:
            clauses.append("(" + " && ".join(and_statements) + ")")
        return " && ".join(clauses)

    def build_exact_match_filter(self, field_name: Text, value: FieldValue) -> Any:
        # json.dumps is called so the string value gets additional quotation marks
        return f"{field_name} == {json.dumps(value)}"

    def build_range_filter(
        self,
        field_name: Text,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        clauses = []
        if lt is not None:
            clauses.append(f"{field_name} < {lt}")
        if gt is not None:
            clauses.append(f"{field_name} > {gt}")
        if lte is not None:
            clauses.append(f"{field_name} <= {lte}")
        if gte is not None:
            clauses.append(f"{field_name} >= {gte}")
        return "(" + " && ".join(clauses) + ")"

    def build_geo_filter(
        self, field_name: Text, lat: float, lon: float, radius: float
    ) -> Any:
        raise IncompatibilityError