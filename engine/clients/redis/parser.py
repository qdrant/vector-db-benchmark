import json
from collections import ChainMap
from typing import Any, Dict, List, Optional, Text, Tuple

from engine.base_client.parser import BaseConditionParser, FieldValue

QueryParamsTuple = Tuple[Text, Dict[Text, Any]]


class RedisConditionParser(BaseConditionParser):
    def __init__(self) -> None:
        super().__init__()
        self.counter = 0

    def build_condition(
        self,
        and_statements: List[QueryParamsTuple],
        or_statements: List[QueryParamsTuple],
    ) -> Tuple[Text, Dict[Text, Any]]:
        if and_statements is None or 0 == len(and_statements):
            and_clauses, and_params = [], []
        else:
            and_clauses, and_params = list(zip(*and_statements))
        if or_statements is None or 0 == len(or_statements):
            or_clauses, or_params = [], []
        else:
            or_clauses, or_params = list(zip(*or_statements))

        clause = []
        if and_clauses is not None and len(and_clauses) > 0:
            clause.append("(" + " ".join(and_clauses) + ")")
        if or_clauses is not None and len(or_clauses) > 0:
            clause.append("(" + " | ".join(or_clauses) + ")")
        params = list(and_params) + list(or_params)
        return " ".join(clause), dict(ChainMap(*params))

    def build_exact_match_filter(self, field_name: Text, value: FieldValue) -> Any:
        param_name = f"{field_name}_{self.counter}"
        self.counter += 1
        return f'@{field_name}:"${param_name}"', {param_name: value}

    def build_range_filter(
        self,
        field_name: Text,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        param_prefix = f"{field_name}_{self.counter}"
        self.counter += 1
        params = {
            f"{param_prefix}_lt": lt,
            f"{param_prefix}_lte": lte,
            f"{param_prefix}_gt": gt,
            f"{param_prefix}_gte": gte,
        }
        filters = [
            ("-inf", f"(${param_prefix}_lt") if lt is not None else None,
            ("-inf", f"${param_prefix}_lte") if lte is not None else None,
            (f"${param_prefix}_gte", "+inf") if gte is not None else None,
            (f"(${param_prefix}_gt", "+inf") if gt is not None else None,
        ]
        clauses = []
        for filter_entry in filters:
            if filter_entry is None:
                continue
            left, right = filter_entry
            clauses.append(f"@{field_name}:[{left} {right}]")
        return " ".join(clauses), params

    def build_geo_filter(
        self, field_name: Text, lat: float, lon: float, radius: float
    ) -> Any:
        param_prefix = f"{field_name}_{self.counter}"
        self.counter += 1
        params = {
            f"{param_prefix}_lon": lon,
            f"{param_prefix}_lat": lat,
            f"{param_prefix}_radius": radius,
        }
        return (
            f"@{field_name}:[${param_prefix}_lon ${param_prefix}_lat ${param_prefix}_radius m]",
            params,
        )
