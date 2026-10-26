import pytest

from engine.base_client import IncompatibilityError
from engine.clients.pgvector.parser import PgVectorConditionParser


@pytest.fixture
def pgvector_condition_parser():
    return PgVectorConditionParser()


def test_parse_returns_none_on_none(pgvector_condition_parser):
    assert pgvector_condition_parser.parse(None) is None


def test_parse_returns_none_on_empty(pgvector_condition_parser):
    assert pgvector_condition_parser.parse({}) is None


def test_parse_converts_exact_match(pgvector_condition_parser):
    sql, params = pgvector_condition_parser.parse(
        {"and": [{"product_group_name": {"match": {"value": "Shoes"}}}]}
    )
    assert sql == '( "product_group_name" = %s )'
    assert params == ["Shoes"]


def test_parse_converts_multiple_or_statements(pgvector_condition_parser):
    sql, params = pgvector_condition_parser.parse(
        {"or": [{"a": {"match": {"value": 80}}}, {"a": {"match": {"value": 2}}}]}
    )
    assert sql == '( "a" = %s OR "a" = %s )'
    assert params == [80, 2]


def test_parse_converts_range_statement(pgvector_condition_parser):
    sql, params = pgvector_condition_parser.parse(
        {"and": [{"a": {"range": {"lt": 10, "gt": -5}}}]}
    )
    assert sql == '( ( "a" < %s AND "a" > %s ) )'
    assert params == [10, -5]


def test_parse_rejects_geo_filter(pgvector_condition_parser):
    with pytest.raises(IncompatibilityError):
        pgvector_condition_parser.parse(
            {
                "and": [
                    {"a": {"geo": {"lat": 1.0, "lon": 2.0, "radius": 1000}}}
                ]
            }
        )
