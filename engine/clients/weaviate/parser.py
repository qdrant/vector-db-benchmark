from typing import Any, Dict, List, Optional

import weaviate.classes as wvc
from weaviate.collections.classes.filters import _Filters

from engine.base_client.parser import BaseConditionParser, FieldValue


class WeaviateConditionParser(BaseConditionParser):
    def parse(self, meta_conditions: Dict[str, Any]) -> Optional[_Filters]:
        if meta_conditions is None or len(meta_conditions) == 0:
            return None
        return super().parse(meta_conditions)

    def build_condition(
        self,
        and_subfilters: Optional[List[_Filters]],
        or_subfilters: Optional[List[_Filters]],
    ) -> Optional[_Filters]:
        weaviate_filter = None
        if or_subfilters is not None and len(or_subfilters) > 0:
            weaviate_filter = or_subfilters[0]
            for filt in or_subfilters[1:]:
                weaviate_filter = weaviate_filter | filt

        if and_subfilters is not None and len(and_subfilters) > 0:
            if weaviate_filter is not None:
                weaviate_filter = and_subfilters[0] & weaviate_filter
            else:
                weaviate_filter = and_subfilters[0]
            for filt in and_subfilters[1:]:
                weaviate_filter = weaviate_filter & filt
        return weaviate_filter

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> _Filters:
        return wvc.query.Filter.by_property(field_name).equal(value)

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        prop = wvc.query.Filter.by_property(field_name)
        ltf = prop.less_than(lt) if lt is not None else None
        ltef = prop.less_or_equal(lte) if lte is not None else None
        gtf = prop.greater_than(gt) if gt is not None else None
        gtef = prop.greater_or_equal(gte) if gte is not None else None
        filtered_lst = list(filter(lambda x: x is not None, [ltf, ltef, gtf, gtef]))
        if len(filtered_lst) == 0:
            return filtered_lst

        result = filtered_lst[0]
        for filt in filtered_lst[1:]:
            result = result & filt
        return result

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> _Filters:
        return wvc.query.Filter.by_property(field_name).within_geo_range(
            distance=radius,
            coordinate=wvc.query.GeoCoordinate(latitude=lat, longitude=lon),
        )
