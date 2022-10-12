from typing import List, Optional

from qdrant_client.http import models as rest


class ConditionParser:
    def parse(self, _meta_conditions) -> Optional[rest.Filter]:
        if _meta_conditions is None or 0 == len(_meta_conditions):
            return None
        return rest.Filter(
            should=self.create_filter_part(_meta_conditions.get("or")),
            must=self.create_filter_part(_meta_conditions.get("and")),
            must_not=None,
        )

    def create_filter_part(self, entries) -> Optional[List[rest.FieldCondition]]:
        if entries is None:
            return None

        conditions = []
        for entry in entries:
            for field_name, filters in entry.items():
                for condition_type, value in filters.items():
                    condition = self.build_field_condition(
                        condition_type, field_name, value
                    )
                    conditions.append(condition)
        return conditions

    def build_field_condition(
        self, condition_type, field_name, value
    ) -> rest.FieldCondition:
        if "match" == condition_type:
            return rest.FieldCondition(
                key=field_name,
                match=rest.MatchValue(value=value.get("value")),
            )
        if "range" == condition_type:
            return rest.FieldCondition(
                key=field_name,
                match=rest.Range(
                    lt=value.get("lt"),
                    gt=value.get("gt"),
                    gte=value.get("gte"),
                    lte=value.get("lte"),
                ),
            )
        if "geo" == condition_type and value.get("radius") is not None:
            return rest.FieldCondition(
                key=field_name,
                geo_radius=rest.GeoRadius(
                    center=rest.GeoPoint(
                        lon=value.get("lon"),
                        lat=value.get("lat"),
                    ),
                    radius=value.get("radius"),
                ),
            )

        raise ValueError(f"Condition type {condition_type} is not supported")
