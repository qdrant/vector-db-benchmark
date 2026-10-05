from typing import Any

from qdrant_client.http import models as rest

from engine.base_client.parser import BaseConditionParser, FieldValue


class QdrantConditionParser(BaseConditionParser):
    def build_condition(
        self, and_subfilters: list[Any] | None, or_subfilters: list[Any] | None
    ) -> Any | None:
        return rest.Filter(
            should=or_subfilters,
            must=and_subfilters,
        )

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        return rest.FieldCondition(
            key=field_name,
            match=rest.MatchValue(value=value),
        )

    def build_match_any_filter(self, field_name: str, values: list[FieldValue]) -> Any:
        return rest.FieldCondition(
            key=field_name,
            match=rest.MatchAny(any=values),
        )

    def build_match_text_filter(self, field_name: str, text: str) -> Any:
        return rest.FieldCondition(
            key=field_name,
            match=rest.MatchText(text=text),
        )

    def build_range_filter(
        self,
        field_name: str,
        lt: FieldValue | None,
        gt: FieldValue | None,
        lte: FieldValue | None,
        gte: FieldValue | None,
    ) -> Any:
        # Any string bound → ISO datetime range; coerce mixed bounds to str.
        if any(isinstance(v, str) for v in (lt, gt, lte, gte) if v is not None):
            lt, gt, lte, gte = (
                None if v is None else str(v) for v in (lt, gt, lte, gte)
            )
            range_obj = rest.DatetimeRange(lt=lt, gt=gt, gte=gte, lte=lte)
        else:
            range_obj = rest.Range(lt=lt, gt=gt, gte=gte, lte=lte)
        return rest.FieldCondition(
            key=field_name,
            range=range_obj,
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
