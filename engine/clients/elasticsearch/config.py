import os

from elasticsearch import Elasticsearch

ELASTIC_PORT = int(os.getenv("ELASTIC_PORT", 9200))
ELASTIC_INDEX = os.getenv("ELASTIC_INDEX", "bench")
ELASTIC_USER = os.getenv("ELASTIC_USER", "elastic")
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD", "passwd")


def get_es_client(host, connection_params):
    init_params = {
        "verify_certs": False,
        "retry_on_timeout": True,
        "ssl_show_warn": False,
        **connection_params,
    }
    client = Elasticsearch(
        f"http://{host}:{ELASTIC_PORT}",
        basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
        **init_params,
    )
    assert client.ping()
    return client
