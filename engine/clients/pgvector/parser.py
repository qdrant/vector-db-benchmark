from typing import Any, Dict, List, Optional, Tuple

from psycopg.types.json import Jsonb

from engine.base_client import IncompatibilityError
from engine.base_client.parser import BaseConditionParser, FieldValue

# (sql_clause, params) — clause references payload fields only through bound
# parameters, never string-interpolated, so values never need manual SQL quoting.
ParsedCondition = Tuple[str, Dict[str, Any]]


class PgVectorConditionParser(BaseConditionParser):
    def __init__(self) -> None:
        super().__init__()
        self._counter = 0

    def _next_param(self) -> str:
        self._counter += 1
        return f"p{self._counter}"

    def build_condition(
        self,
        and_subfilters: Optional[List[ParsedCondition]],
        or_subfilters: Optional[List[ParsedCondition]],
    ) -> Optional[ParsedCondition]:
        clauses = []
        params: Dict[str, Any] = {}

        if or_subfilters:
            sub_clauses, sub_params = zip(*or_subfilters)
            clauses.append("( " + " OR ".join(sub_clauses) + " )")
            for p in sub_params:
                params.update(p)
        if and_subfilters:
            sub_clauses, sub_params = zip(*and_subfilters)
            clauses.append("( " + " AND ".join(sub_clauses) + " )")
            for p in sub_params:
                params.update(p)

        return " AND ".join(clauses), params

    def build_exact_match_filter(
        self, field_name: str, value: FieldValue
    ) -> ParsedCondition:
        key_param = self._next_param()
        value_param = self._next_param()
        # `@>` not `=`: equality for scalar fields, "contains" for list-valued
        # fields (e.g. arxiv `labels`), same semantics as Qdrant MatchValue and
        # Elasticsearch `match` on an array.
        return (
            f"payload -> %({key_param})s @> %({value_param})s",
            {key_param: field_name, value_param: Jsonb(value)},
        )

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> ParsedCondition:
        clauses = []
        params: Dict[str, Any] = {}
        for op, bound in (("<", lt), (">", gt), ("<=", lte), (">=", gte)):
            if bound is None:
                continue
            key_param = self._next_param()
            value_param = self._next_param()
            clauses.append(f"payload -> %({key_param})s {op} %({value_param})s")
            params[key_param] = field_name
            params[value_param] = Jsonb(bound)
        return "( " + " AND ".join(clauses) + " )", params

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        # payload is a flat JSONB blob, no geo type/indexing support
        raise IncompatibilityError
