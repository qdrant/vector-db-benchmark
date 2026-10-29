from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from engine.base_client import IncompatibilityError
from engine.base_client.distances import Distance
from engine.clients.elasticsearch import configure
from engine.clients.elasticsearch.configure import (
    MAX_DENSE_VECTOR_DIMS,
    ElasticConfigurator,
)


@pytest.fixture
def client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(configure, "get_es_client", lambda host, params: client)
    return client


@pytest.fixture
def configurator(client):
    return ElasticConfigurator("localhost", {"index_options": {}}, {})


def make_dataset(vector_size, distance=Distance.COSINE):
    return SimpleNamespace(
        config=SimpleNamespace(vector_size=vector_size, distance=distance, schema={})
    )


def test_max_dense_vector_dims_matches_elasticsearch_limit():
    assert MAX_DENSE_VECTOR_DIMS == 4096


@pytest.mark.parametrize("vector_size", [128, 2048, 2049, 4096])
def test_recreate_accepts_vectors_up_to_the_limit(configurator, client, vector_size):
    configurator.recreate(make_dataset(vector_size), {"index_options": {}})

    client.indices.create.assert_called_once()
    mappings = client.indices.create.call_args.kwargs["mappings"]
    assert mappings["properties"]["vector"]["dims"] == vector_size


@pytest.mark.parametrize("vector_size", [4097, 8192])
def test_recreate_rejects_vectors_above_the_limit(configurator, client, vector_size):
    with pytest.raises(IncompatibilityError):
        configurator.recreate(make_dataset(vector_size), {"index_options": {}})

    client.indices.create.assert_not_called()


def test_recreate_still_rejects_dot_distance(configurator, client):
    with pytest.raises(IncompatibilityError):
        configurator.recreate(make_dataset(128, Distance.DOT), {"index_options": {}})

    client.indices.create.assert_not_called()
