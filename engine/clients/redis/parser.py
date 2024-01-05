from collections import ChainMap
from typing import Any, Dict, List, Optional, Tuple

from engine.base_client.parser import BaseConditionParser, FieldValue
from engine.clients.redis.helper import convert_to_redis_coords

QueryParamsTuple = Tuple[str, Dict[str, Any]]


class RedisConditionParser(BaseConditionParser):
    def __init__(self) -> None:
        super().__init__()
        self.counter = 0

    def build_condition(
        self,
        and_subfilters: Optional[List[QueryParamsTuple]],
        or_subfilters: Optional[List[QueryParamsTuple]],
    ) -> Tuple[str, Dict[str, Any]]:
        and_clauses, and_params = (
            list(zip(*and_subfilters)) if and_subfilters else ([], [])
        )
        or_clauses, or_params = list(zip(*or_subfilters)) if or_subfilters else ([], [])

        clause = []
        if len(and_clauses) > 0:
            clause.append("(" + " ".join(and_clauses) + ")")
        if len(or_clauses) > 0:
            clause.append("(" + " | ".join(or_clauses) + ")")
        params = list(and_params) + list(or_params)
        return " ".join(clause), dict(ChainMap(*params))

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        param_name = f"{field_name}_{self.counter}"
        self.counter += 1
        if isinstance(value, str):
            return f"@{field_name}:{{${param_name}}}", {param_name: value}
        # field is numeric, value is an integer
        return f"@{field_name}:[${param_name} ${param_name}]", {param_name: value}

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        param_prefix = f"{field_name}_{self.counter}"
        self.counter += 1
        params = dict()
        filters = list()

        if lt is not None:
            params[f"{param_prefix}_lt"] = lt
            filters.append(("-inf", f"(${param_prefix}_lt"))

        if gt is not None:
            params[f"{param_prefix}_gt"] = gt
            filters.append((f"(${param_prefix}_gt", "+inf"))

        if lte is not None:
            params[f"{param_prefix}_lte"] = lte
            filters.append(("-inf", f"${param_prefix}_lte"))

        if gte is not None:
            params[f"{param_prefix}_gte"] = gte
            filters.append((f"${param_prefix}_gte", "+inf"))

        clauses = []
        for filter_entry in filters:
            if filter_entry is None:
                continue
            left, right = filter_entry
            clauses.append(f"@{field_name}:[{left} {right}]")

        return " ".join(clauses), params

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        param_prefix = f"{field_name}_{self.counter}"
        self.counter += 1
        lon, lat = convert_to_redis_coords(lon, lat)
        params = {
            f"{param_prefix}_lon": lon,
            f"{param_prefix}_lat": lat,
            f"{param_prefix}_radius": radius,
        }
        return (
            f"@{field_name}:[${param_prefix}_lon ${param_prefix}_lat ${param_prefix}_radius m]",
            params,
        )
