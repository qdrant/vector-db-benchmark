import json
from typing import Any

from engine.base_client import IncompatibilityError
from engine.base_client.parser import BaseConditionParser, FieldValue


class PgVectorConditionParser(BaseConditionParser):
    def build_condition(
        self, and_subfilters: list[Any] | None, or_subfilters: list[Any] | None
    ) -> Any | None:
        clauses = []
        if or_subfilters is not None and len(or_subfilters) > 0:
            clauses.append(f"( {' OR '.join(or_subfilters)} )")
        if and_subfilters is not None and len(and_subfilters) > 0:
            clauses.append(f"( {' AND '.join(and_subfilters)} )")

        return " AND ".join(clauses)

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        return f"{field_name} == {json.dumps(value)}"

    def build_range_filter(
        self,
        field_name: str,
        lt: FieldValue | None,
        gt: FieldValue | None,
        lte: FieldValue | None,
        gte: FieldValue | None,
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
        return f"( {' AND '.join(clauses)} )"

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        # TODO: Implement this
        raise IncompatibilityError
