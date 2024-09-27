from typing import List, Optional

from chromadb import Where
from chromadb.types import OperatorExpression

from engine.base_client import IncompatibilityError
from engine.base_client.parser import BaseConditionParser, FieldValue


class ChromaConditionParser(BaseConditionParser):
    def build_condition(
        self,
        and_subfilters: Optional[List[Where]],
        or_subfilters: Optional[List[Where]],
    ) -> Where:
        condition: Where = {}
        if and_subfilters is not None:
            if len(and_subfilters) >= 2:
                condition["$and"] = and_subfilters
            elif len(and_subfilters) == 1:
                condition = {**condition, **and_subfilters[0]}

        if or_subfilters is not None:
            if len(or_subfilters) >= 2:
                condition["$or"] = or_subfilters
            elif len(or_subfilters) == 1:
                condition = {**condition, **or_subfilters[0]}

        return condition
        # return {k: v for d in [flt for xs in [and_subfilters, or_subfilters] for flt in xs] for k, v in d.items()}

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Where:
        return {field_name: value}

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Where:
        raw_filters: OperatorExpression = {
            "$lt": lt,
            "$gt": gt,
            "$lte": lte,
            "$gte": gte,
        }
        filters: OperatorExpression = {
            k: v for k, v in raw_filters.items() if v is not None
        }
        return {field_name: filters}

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Where:
        raise IncompatibilityError
