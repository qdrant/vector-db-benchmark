from qdrant_client.http import models as rest

from engine.clients.qdrant.parser import QdrantConditionParser


def test_parse_returns_none_on_none():
    parser = QdrantConditionParser()
    qdrant_filter = parser.parse(None)
    assert qdrant_filter is None


def test_parse_returns_none_on_empty():
    conditions = {}
    parser = QdrantConditionParser()
    qdrant_filter = parser.parse(conditions)
    assert qdrant_filter is None


def test_parse_converts_exact_match():
    conditions = {"and": [{"product_group_name": {"match": {"value": "Shoes"}}}]}
    parser = QdrantConditionParser()
    qdrant_filter = parser.parse(conditions)

    assert qdrant_filter is not None
    assert qdrant_filter.should is None
    assert qdrant_filter.must is not None
    assert qdrant_filter.must_not is None
    assert 1 == len(qdrant_filter.must)
    condition = qdrant_filter.must[0]
    assert isinstance(condition, rest.FieldCondition)
    assert (
        rest.FieldCondition(
            key="product_group_name", match=rest.MatchValue(value="Shoes")
        )
        == condition
    )


def test_parse_converts_multiple_or_statements():
    conditions = {
        "or": [{"a": {"match": {"value": 80}}}, {"a": {"match": {"value": 2}}}]
    }
    parser = QdrantConditionParser()
    qdrant_filter = parser.parse(conditions)

    assert qdrant_filter is not None
    assert qdrant_filter.should is not None
    assert qdrant_filter.must is None
    assert qdrant_filter.must_not is None
    assert 2 == len(qdrant_filter.should)
    first_condition, second_condition = qdrant_filter.should
    assert isinstance(first_condition, rest.FieldCondition)
    assert (
        rest.FieldCondition(key="a", match=rest.MatchValue(value=80)) == first_condition
    )
    assert (
        rest.FieldCondition(key="a", match=rest.MatchValue(value=2)) == second_condition
    )


def test_parse_converts_geo_statement():
    conditions = {
        "and": [
            {
                "a": {
                    "geo": {
                        "lon": 116.93930970419757,
                        "lat": -52.30987113579712,
                        "radius": 326341,
                    }
                }
            }
        ]
    }
    parser = QdrantConditionParser()
    qdrant_filter = parser.parse(conditions)

    assert qdrant_filter is not None
    assert qdrant_filter.should is None
    assert qdrant_filter.must is not None
    assert qdrant_filter.must_not is None
    assert 1 == len(qdrant_filter.must)
    assert 1 == len(qdrant_filter.must)
    condition = qdrant_filter.must[0]
    assert isinstance(condition, rest.FieldCondition)
    assert (
        rest.FieldCondition(
            key="a",
            geo_radius=rest.GeoRadius(
                center=rest.GeoPoint(
                    lon=116.93930970419757,
                    lat=-52.30987113579712,
                ),
                radius=326341,
            ),
        )
        == condition
    )
