from datetime import datetime, timezone

import pytest
from qdrant_client.http import models as rest

from engine.clients.qdrant.parser import QdrantConditionParser


@pytest.fixture
def qdrant_condition_parser():
    return QdrantConditionParser()


def test_parse_returns_none_on_none(qdrant_condition_parser):
    qdrant_filter = qdrant_condition_parser.parse(None)
    assert qdrant_filter is None


def test_parse_returns_none_on_empty(qdrant_condition_parser):
    conditions = {}
    qdrant_filter = qdrant_condition_parser.parse(conditions)
    assert qdrant_filter is None


def test_parse_converts_exact_match(qdrant_condition_parser):
    conditions = {"and": [{"product_group_name": {"match": {"value": "Shoes"}}}]}
    qdrant_filter = qdrant_condition_parser.parse(conditions)

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


def test_parse_converts_multiple_or_statements(qdrant_condition_parser):
    conditions = {
        "or": [{"a": {"match": {"value": 80}}}, {"a": {"match": {"value": 2}}}]
    }
    qdrant_filter = qdrant_condition_parser.parse(conditions)

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


def test_parse_converts_fineweb_text_and_structured_filters(qdrant_condition_parser):
    conditions = {
        "and": [
            {"text": {"match_text": {"text": "climate change"}}},
            {"domain": {"match_any": {"any": ["example.com", "news.org"]}}},
            {"language_score": {"range": {"gte": 0.9}}},
            {
                "date": {
                    "range": {
                        "gte": "2018-01-01T00:00:00Z",
                        "lt": "2019-01-01T00:00:00Z",
                    }
                }
            },
        ]
    }
    qdrant_filter = qdrant_condition_parser.parse(conditions)
    assert qdrant_filter is not None
    assert 4 == len(qdrant_filter.must)
    text, domain, score, date = qdrant_filter.must
    assert text.match.text == "climate change"
    assert domain.match.any == ["example.com", "news.org"]
    assert score.range.gte == 0.9
    assert date.range.gte == datetime(2018, 1, 1, tzinfo=timezone.utc)
    assert date.range.lt == datetime(2019, 1, 1, tzinfo=timezone.utc)


def test_parse_converts_geo_statement(qdrant_condition_parser):
    conditions = {
        "and": [
            {
                "a": {
                    "geo": {
                        "lon": 116.0,
                        "lat": -52.0,
                        "radius": 326341,
                    }
                }
            }
        ]
    }
    qdrant_filter = qdrant_condition_parser.parse(conditions)

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
                    lon=116.0,
                    lat=-52.0,
                ),
                radius=326341,
            ),
        )
        == condition
    )
