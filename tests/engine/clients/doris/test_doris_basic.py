import pytest

from engine.clients.client_factory import ClientFactory


@pytest.mark.skip(reason="Requires running Doris instance; integration test skipped by default")
def test_doris_factory_registration():
    factory = ClientFactory(host="localhost")
    experiment = {
        "name": "doris-basic",
        "engine": "doris",
        "connection_params": {"host": "localhost", "query_port": 9030},
        "collection_params": {"database": "benchmark", "table_name": "vectors"},
        "upload_params": {"batch_size": 2},
        "search_params": [{"top": 5}],
    }

    client = factory.build_client(experiment)
    assert client.engine == "doris"
    assert client.configurator is not None
    assert client.uploader is not None
    assert client.searchers, "Searchers list should not be empty"