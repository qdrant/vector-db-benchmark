import pytest
from psycopg.types.json import Jsonb

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
    conditions = {"and": [{"product_group_name": {"match": {"value": "Shoes"}}}]}
    clause, params = pgvector_condition_parser.parse(conditions)

    # `@>` so a list-valued payload field ("contains") matches too, not just scalars
    assert "( payload -> %(p1)s @> %(p2)s )" == clause
    assert "product_group_name" == params["p1"]
    assert isinstance(params["p2"], Jsonb)
    assert "Shoes" == params["p2"].obj


def test_parse_converts_multiple_or_statements(pgvector_condition_parser):
    conditions = {
        "or": [{"a": {"match": {"value": 80}}}, {"a": {"match": {"value": 2}}}]
    }
    clause, params = pgvector_condition_parser.parse(conditions)

    assert "( payload -> %(p1)s @> %(p2)s OR payload -> %(p3)s @> %(p4)s )" == clause
    assert "a" == params["p1"] == params["p3"]
    assert 80 == params["p2"].obj
    assert 2 == params["p4"].obj


def test_parse_converts_range(pgvector_condition_parser):
    conditions = {"and": [{"price": {"range": {"gte": 10, "lt": 20}}}]}
    clause, params = pgvector_condition_parser.parse(conditions)

    # bounds are emitted in (lt, gt, lte, gte) order
    assert (
        "( ( payload -> %(p1)s < %(p2)s AND payload -> %(p3)s >= %(p4)s ) )" == clause
    )
    assert "price" == params["p1"] == params["p3"]
    assert 20 == params["p2"].obj
    assert 10 == params["p4"].obj


def test_parse_combines_and_and_or(pgvector_condition_parser):
    conditions = {
        "and": [{"a": {"match": {"value": 1}}}],
        "or": [{"b": {"match": {"value": 2}}}, {"b": {"match": {"value": 3}}}],
    }
    clause, params = pgvector_condition_parser.parse(conditions)

    assert (
        "( payload -> %(p3)s @> %(p4)s OR payload -> %(p5)s @> %(p6)s )"
        " AND ( payload -> %(p1)s @> %(p2)s )" == clause
    )
    assert {"p1": "a", "p3": "b", "p5": "b"} == {
        k: v for k, v in params.items() if not isinstance(v, Jsonb)
    }


def test_parse_geo_raises_incompatibility(pgvector_condition_parser):
    conditions = {
        "and": [{"a": {"geo": {"lon": 116.0, "lat": -52.0, "radius": 326341}}}]
    }
    with pytest.raises(IncompatibilityError):
        pgvector_condition_parser.parse(conditions)
