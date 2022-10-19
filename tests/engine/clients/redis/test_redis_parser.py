from engine.clients.redis.parser import RedisConditionParser


def test_parse_returns_none_on_none():
    parser = RedisConditionParser()
    redis_filter = parser.parse(None)
    assert redis_filter is None


def test_parse_returns_none_on_empty():
    conditions = {}
    parser = RedisConditionParser()
    redis_filter = parser.parse(conditions)
    assert redis_filter is None


def test_parse_converts_exact_match():
    conditions = {"and": [{"product_group_name": {"match": {"value": "Shoes"}}}]}
    parser = RedisConditionParser()
    redis_filter, params = parser.parse(conditions)

    assert '(@product_group_name:"$product_group_name_0")' == redis_filter
    assert "Shoes" == params.get("product_group_name_0")


def test_parse_converts_multiple_or_statements():
    conditions = {
        "or": [{"a": {"match": {"value": 80}}}, {"a": {"match": {"value": 2}}}]
    }
    parser = RedisConditionParser()
    redis_filter, params = parser.parse(conditions)

    assert '(@a:"$a_0" | @a:"$a_1")' == redis_filter
    assert 80 in params.values()
    assert 2 in params.values()


def test_parse_converts_range_statement():
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
    parser = RedisConditionParser()
    redis_filter, params = parser.parse(conditions)

    assert "(@a:[-inf ($a_0_lt] @a:[($a_0_gt +inf])" == redis_filter
    assert 10 == params.get("a_0_lt")
    assert -5 == params.get("a_0_gt")


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
    parser = RedisConditionParser()
    redis_filter, params = parser.parse(conditions)

    assert "(@a:[$a_0_lon $a_0_lat $a_0_radius m])" == redis_filter
    assert 116.93930970419757 == params.get("a_0_lon")
    assert -52.30987113579712 == params.get("a_0_lat")
    assert 326341 == params.get("a_0_radius")
