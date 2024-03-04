import os

from elasticsearch import Elasticsearch

ELASTIC_PORT = int(os.getenv("ELASTIC_PORT", 9200))
ELASTIC_INDEX = os.getenv("ELASTIC_INDEX", "bench")
ELASTIC_USER = os.getenv("ELASTIC_USER", "elastic")
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD", "passwd")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY", None)
ELASTIC_TIMEOUT = int(os.getenv("ELASTIC_TIMEOUT", 90))


def get_es_client(host, connection_params):
    client: Elasticsearch = None
    init_params = {
        **{
            "verify_certs": False,
            "request_timeout": ELASTIC_TIMEOUT,
            "retry_on_timeout": True,
        },
        **connection_params,
    }
    if host.startswith("http"):
        url = ""
    else:
        url = "http://"
    url += f"{host}:{ELASTIC_PORT}"
    if ELASTIC_API_KEY is None:
        client = Elasticsearch(
            url,
            basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
            **init_params,
        )
    else:
        client = Elasticsearch(
            url,
            api_key=ELASTIC_API_KEY,
            **init_params,
        )
    return client
