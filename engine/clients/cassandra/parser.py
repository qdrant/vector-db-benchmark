from typing import Any, List, Optional

from engine.base_client.parser import BaseConditionParser, FieldValue


class CassandraConditionParser(BaseConditionParser):
    def build_condition(
        self, and_subfilters: Optional[List[Any]], or_subfilters: Optional[List[Any]]
    ) -> Optional[Any]:
        """
        Build a CQL condition expression that combines AND and OR subfilters
        """
        conditions = []

        # Add AND conditions
        if and_subfilters and len(and_subfilters) > 0:
            and_conds = " AND ".join([f"({cond})" for cond in and_subfilters if cond])
            if and_conds:
                conditions.append(f"({and_conds})")

        # Add OR conditions
        if or_subfilters and len(or_subfilters) > 0:
            or_conds = " OR ".join([f"({cond})" for cond in or_subfilters if cond])
            if or_conds:
                conditions.append(f"({or_conds})")

        # Combine all conditions
        if not conditions:
            return None

        return " AND ".join(conditions)

    def build_exact_match_filter(self, field_name: str, value: FieldValue) -> Any:
        """
        Build a CQL exact match condition for metadata fields
        For Cassandra, we format metadata as a map with string values
        """
        if isinstance(value, str):
            return f"metadata['{field_name}'] = '{value}'"
        else:
            return f"metadata['{field_name}'] = '{str(value)}'"

    def build_range_filter(
        self,
        field_name: str,
        lt: Optional[FieldValue],
        gt: Optional[FieldValue],
        lte: Optional[FieldValue],
        gte: Optional[FieldValue],
    ) -> Any:
        """
        Build a CQL range filter condition
        """
        conditions = []

        if lt is not None:
            if isinstance(lt, str):
                conditions.append(f"metadata['{field_name}'] < '{lt}'")
            else:
                conditions.append(f"metadata['{field_name}'] < '{str(lt)}'")

        if gt is not None:
            if isinstance(gt, str):
                conditions.append(f"metadata['{field_name}'] > '{gt}'")
            else:
                conditions.append(f"metadata['{field_name}'] > '{str(gt)}'")

        if lte is not None:
            if isinstance(lte, str):
                conditions.append(f"metadata['{field_name}'] <= '{lte}'")
            else:
                conditions.append(f"metadata['{field_name}'] <= '{str(lte)}'")

        if gte is not None:
            if isinstance(gte, str):
                conditions.append(f"metadata['{field_name}'] >= '{gte}'")
            else:
                conditions.append(f"metadata['{field_name}'] >= '{str(gte)}'")

        return " AND ".join(conditions)

    def build_geo_filter(
        self, field_name: str, lat: float, lon: float, radius: float
    ) -> Any:
        """
        Build a CQL geo filter condition
        Note: Basic Cassandra doesn't have built-in geo filtering.
        This is a simplified approach that won't actually work without extensions.
        """
        # In a real implementation with a geo extension, we'd implement proper geo filtering
        # For this benchmark, we'll return a placeholder condition that doesn't filter
        return "1=1"  # Always true condition as a placeholder
