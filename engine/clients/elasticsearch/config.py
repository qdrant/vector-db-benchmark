import os
import time

import urllib3
from elasticsearch import Elasticsearch

ELASTIC_PORT = int(os.getenv("ELASTIC_PORT", 9200))
ELASTIC_INDEX = os.getenv("ELASTIC_INDEX", "bench")
ELASTIC_USER = os.getenv("ELASTIC_USER", "elastic")
ELASTIC_PASSWORD = os.getenv("ELASTIC_PASSWORD", "passwd")

ELASTIC_TIMEOUT = int(os.getenv("ELASTIC_TIMEOUT", 300))
ELASTIC_INDEX_TIMEOUT = os.getenv("ELASTIC_INDEX_TIMEOUT", "30m")
ELASTIC_INDEX_REFRESH_INTERVAL = os.getenv("ELASTIC_INDEX_REFRESH_INTERVAL", "-1")


def get_es_client(host, connection_params):
    client: Elasticsearch = None
    init_params = {
        "verify_certs": False,
        "request_timeout": ELASTIC_TIMEOUT,
        "retry_on_timeout": True,
        "ssl_show_warn": False,
        **connection_params,
    }
    client = Elasticsearch(
        f"http://{host}:{ELASTIC_PORT}",
        basic_auth=(ELASTIC_USER, ELASTIC_PASSWORD),
        **init_params,
    )
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    assert client.ping()
    return client


def _wait_for_es_status(client, status="yellow"):
    print(f"waiting for ES {status} status...")
    for _ in range(100):
        try:
            client.cluster.health(wait_for_status=status)
            return client
        except ConnectionError:
            time.sleep(0.1)
    else:
        # timeout
        raise Exception("Elasticsearch failed to start.")
