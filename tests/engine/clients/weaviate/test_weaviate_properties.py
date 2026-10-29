import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from dataset_reader.base_reader import Record
from engine.base_client.distances import Distance
from engine.clients.weaviate import configure as weaviate_configure
from engine.clients.weaviate.configure import WeaviateConfigurator
from engine.clients.weaviate.parser import WeaviateConditionParser
from engine.clients.weaviate.properties import (
    RESERVED_PROPERTY_NAMES,
    property_name,
    rename_properties,
)
from engine.clients.weaviate.upload import WeaviateUploader


def test_reserved_names_match_weaviate_list():
    assert RESERVED_PROPERTY_NAMES == {"_additional", "_id", "id"}


@pytest.mark.parametrize(
    "name", ["update_date_ts", "labels", "Id", "ID", "id_", "my_id", "_idx", "_"]
)
def test_property_name_keeps_regular_names(name):
    assert property_name(name) == name


@pytest.mark.parametrize("name", sorted(RESERVED_PROPERTY_NAMES))
def test_property_name_renames_reserved_names(name):
    renamed = property_name(name)
    assert renamed != name
    assert renamed not in RESERVED_PROPERTY_NAMES
    assert property_name(name) == renamed  # deterministic


def test_rename_properties_empty():
    assert rename_properties({}) == {}


def test_rename_properties_keeps_regular_names_and_values():
    props = {"labels": "cs.AI", "update_date_ts": 5}
    assert rename_properties(props) == props


def test_rename_properties_renames_only_reserved_keys():
    props = {"labels": "cs.AI", "id": "a1", "_id": "b2", "_additional": 3}
    assert rename_properties(props) == {
        "labels": "cs.AI",
        property_name("id"): "a1",
        property_name("_id"): "b2",
        property_name("_additional"): 3,
    }


def test_rename_properties_does_not_mutate_input():
    props = {"id": "a1"}
    rename_properties(props)
    assert props == {"id": "a1"}


def test_rename_properties_detects_collisions():
    with pytest.raises(ValueError):
        rename_properties({"id": "a", property_name("id"): "b"})


# configure


@pytest.fixture
def client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(
        weaviate_configure, "WeaviateClient", lambda *args, **kwargs: client
    )
    return client


def recreate(client, schema):
    configurator = WeaviateConfigurator("localhost", {}, {})
    dataset = SimpleNamespace(
        config=SimpleNamespace(distance=Distance.COSINE, schema=schema)
    )
    configurator.recreate(dataset, {"vectorIndexConfig": {}})
    client.collections.create_from_dict.assert_called_once()
    return client.collections.create_from_dict.call_args.args[0]["properties"]


def test_configure_renames_reserved_schema_fields(client):
    properties = recreate(
        client,
        {"update_date_ts": "int", "labels": "keyword", "id": "keyword"},
    )
    assert [(p["name"], p["dataType"]) for p in properties] == [
        ("update_date_ts", ["int"]),
        ("labels", ["string"]),
        (property_name("id"), ["string"]),
    ]


def test_configure_never_sends_reserved_names(client):
    properties = recreate(
        client, {"id": "keyword", "_id": "int", "_additional": "text", "a": "float"}
    )
    names = {p["name"] for p in properties}
    assert not names & RESERVED_PROPERTY_NAMES
    assert len(names) == 4


def test_configure_empty_schema(client):
    assert recreate(client, {}) == []


# upload


@pytest.fixture
def collection():
    collection = MagicMock()
    WeaviateUploader.collection = collection
    yield collection
    WeaviateUploader.collection = None


def uploaded_objects(collection):
    collection.data.insert_many.assert_called_once()
    return collection.data.insert_many.call_args.args[0]


def test_upload_renames_reserved_metadata_keys(collection):
    WeaviateUploader.upload_batch(
        [
            Record(
                id=1,
                vector=[0.1],
                sparse_vector=None,
                metadata={"id": "a1", "labels": "cs.AI"},
            )
        ]
    )
    (obj,) = uploaded_objects(collection)
    assert obj.properties == {property_name("id"): "a1", "labels": "cs.AI"}
    assert obj.uuid == uuid.UUID(int=1)
    assert obj.vector == [0.1]


def test_upload_matches_configured_schema(client, collection):
    schema = {"id": "keyword", "labels": "keyword"}
    configured = {p["name"] for p in recreate(client, schema)}
    WeaviateUploader.upload_batch(
        [
            Record(
                id=2,
                vector=[0.2],
                sparse_vector=None,
                metadata={"id": "a1", "labels": "x"},
            )
        ]
    )
    (obj,) = uploaded_objects(collection)
    assert set(obj.properties) == configured


@pytest.mark.parametrize("metadata", [None, {}])
def test_upload_without_metadata(collection, metadata):
    WeaviateUploader.upload_batch(
        [Record(id=3, vector=[0.3], sparse_vector=None, metadata=metadata)]
    )
    (obj,) = uploaded_objects(collection)
    assert obj.properties == {}


def test_upload_empty_batch(collection):
    WeaviateUploader.upload_batch([])
    collection.data.insert_many.assert_not_called()


# parser


@pytest.fixture
def parser():
    return WeaviateConditionParser()


def test_parse_keeps_regular_field_name(parser):
    flt = parser.parse({"and": [{"labels": {"match": {"value": "cs.AI"}}}]})
    assert flt.target == "labels"
    assert flt.value == "cs.AI"


def test_parse_renames_reserved_field_in_exact_match(parser):
    flt = parser.parse({"and": [{"id": {"match": {"value": "a1"}}}]})
    assert flt.target == property_name("id")
    assert flt.value == "a1"


def test_parse_renames_reserved_field_in_range(parser):
    flt = parser.parse({"and": [{"_id": {"range": {"gt": 1}}}]})
    assert flt.target == property_name("_id")
    assert flt.value == 1


def test_parse_renames_reserved_fields_in_combined_conditions(parser):
    flt = parser.parse(
        {
            "and": [{"id": {"match": {"value": "a1"}}}],
            "or": [
                {"labels": {"match": {"value": "x"}}},
                {"_additional": {"match": {"value": "y"}}},
            ],
        }
    )
    targets = []

    def collect(node):
        if hasattr(node, "filters"):
            for child in node.filters:
                collect(child)
        else:
            targets.append(node.target)

    collect(flt)
    assert sorted(targets) == sorted(
        [property_name("id"), "labels", property_name("_additional")]
    )


def test_parse_renames_reserved_field_in_geo_filter(parser):
    flt = parser.parse(
        {"and": [{"id": {"geo": {"lat": 1.0, "lon": 2.0, "radius": 3.0}}}]}
    )
    assert flt.target == property_name("id")


@pytest.mark.parametrize("conditions", [None, {}])
def test_parse_empty_conditions(parser, conditions):
    assert parser.parse(conditions) is None


def test_filter_target_matches_configured_field(client, parser):
    configured = {p["name"] for p in recreate(client, {"id": "keyword"})}
    flt = parser.parse({"and": [{"id": {"match": {"value": "a1"}}}]})
    assert flt.target in configured
