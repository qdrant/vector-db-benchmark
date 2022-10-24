from typing import Any, List, Optional

from qdrant_client.http import models as rest

from engine.base_client.parser import BaseConditionParser, FieldValue


class QdrantConditionParser(BaseConditionParser):
    def build_condition(
        self, and_subfilters: Optional[List[Any]], or_subfilters: Optional[List[Any]]
    ) -> Optional[Any]:
        return rest.Filter(
            should=or_subfilters,
            must=and_subfilters,
        )

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        return rest.FieldCondition(
            key=field_name,
            match=rest.MatchValue(value=value),
        )

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        return rest.FieldCondition(
            key=field_name,
            range=rest.Range(
                lt=lt,
                gt=gt,
                gte=gte,
                lte=lte,
            ),
        )

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        return rest.FieldCondition(
            key=field_name,
            geo_radius=rest.GeoRadius(
                center=rest.GeoPoint(
                    lon=lon,
                    lat=lat,
                ),
                radius=radius,
            ),
        )
