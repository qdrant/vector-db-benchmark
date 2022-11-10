import pytest

from engine.clients.redis.parser import RedisConditionParser


@pytest.fixture
def redis_condition_parser():
    return RedisConditionParser()


def test_parse_returns_none_on_none(redis_condition_parser):
    redis_filter = redis_condition_parser.parse(None)
    assert redis_filter is None


def test_parse_returns_none_on_empty(redis_condition_parser):
    conditions = {}
    redis_filter = redis_condition_parser.parse(conditions)
    assert redis_filter is None


def test_parse_converts_exact_match(redis_condition_parser):
    conditions = {"and": [{"product_group_name": {"match": {"value": "Shoes"}}}]}
    redis_filter, params = redis_condition_parser.parse(conditions)

    assert '(@product_group_name:"$product_group_name_0")' == redis_filter
    assert "Shoes" == params.get("product_group_name_0")


def test_parse_converts_multiple_or_statements(redis_condition_parser):
    conditions = {
        "or": [{"a": {"match": {"value": 80}}}, {"a": {"match": {"value": 2}}}]
    }
    redis_filter, params = redis_condition_parser.parse(conditions)

    assert "(@a:[$a_0 $a_0] | @a:[$a_1 $a_1])" == redis_filter
    assert 80 in params.values()
    assert 2 in params.values()


def test_parse_converts_range_statement(redis_condition_parser):
    conditions = {
        "and": [
            {
                "a": {
                    "range": {
                        "lt": 10,
                        "gt": -5,
                    }
                }
            }
        ]
    }
    redis_filter, params = redis_condition_parser.parse(conditions)

    assert "(@a:[-inf ($a_0_lt] @a:[($a_0_gt +inf])" == redis_filter
    assert 10 == params.get("a_0_lt")
    assert -5 == params.get("a_0_gt")


def test_parse_converts_geo_statement(redis_condition_parser):
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
    redis_filter, params = redis_condition_parser.parse(conditions)

    assert "(@a:[$a_0_lon $a_0_lat $a_0_radius m])" == redis_filter
    assert 116.0 == params.get("a_0_lon")
    assert -52.0 == params.get("a_0_lat")
    assert 326341 == params.get("a_0_radius")
