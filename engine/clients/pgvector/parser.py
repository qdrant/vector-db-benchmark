from typing import Any, List, Optional, Tuple

from engine.base_client import IncompatibilityError
from engine.base_client.parser import BaseConditionParser, FieldValue
from engine.clients.pgvector.config import quote_ident

SqlCondition = Tuple[str, List[Any]]


class PgVectorConditionParser(BaseConditionParser):
    def build_condition(
        self, and_subfilters: Optional[List[Any]], or_subfilters: Optional[List[Any]]
    ) -> Optional[Any]:
        clauses: List[str] = []
        params: List[Any] = []
        if or_subfilters:
            sqls, extra = self._join(or_subfilters, " OR ")
            clauses.append(f"( {sqls} )")
            params.extend(extra)
        if and_subfilters:
            sqls, extra = self._join(and_subfilters, " AND ")
            clauses.append(f"( {sqls} )")
            params.extend(extra)
        if not clauses:
            return None
        return " AND ".join(clauses), params

    @staticmethod
    def _join(filters: List[SqlCondition], sep: str) -> SqlCondition:
        sqls = []
        params: List[Any] = []
        for sql, extra in filters:
            sqls.append(sql)
            params.extend(extra)
        return sep.join(sqls), params

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        return f"{quote_ident(field_name)} = %s", [value]

    def build_match_any_filter(self, field_name: str, values: List[FieldValue]) -> Any:
        placeholders = ", ".join(["%s"] * len(values))
        return f"{quote_ident(field_name)} IN ({placeholders})", list(values)

    def build_match_text_filter(self, field_name: str, text: str) -> Any:
        return f"{quote_ident(field_name)} ILIKE %s", [f"%{text}%"]

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        ident = quote_ident(field_name)
        clauses = []
        params: List[Any] = []
        if lt is not None:
            clauses.append(f"{ident} < %s")
            params.append(lt)
        if gt is not None:
            clauses.append(f"{ident} > %s")
            params.append(gt)
        if lte is not None:
            clauses.append(f"{ident} <= %s")
            params.append(lte)
        if gte is not None:
            clauses.append(f"{ident} >= %s")
            params.append(gte)
        return f"( {' AND '.join(clauses)} )", params

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        raise IncompatibilityError
