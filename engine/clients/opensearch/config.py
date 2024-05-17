import os
import time

from opensearchpy import OpenSearch

OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", 9200))
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "bench")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "opensearch")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "passwd")
OPENSEARCH_TIMEOUT = int(os.getenv("OPENSEARCH_TIMEOUT", 300))
OPENSEARCH_INDEX_TIMEOUT = int(os.getenv("OPENSEARCH_INDEX_TIMEOUT", 300))


def get_opensearch_client(host, connection_params):
    init_params = {
        **{
            "verify_certs": False,
            "request_timeout": OPENSEARCH_TIMEOUT,
            "retry_on_timeout": True,
            # don't show warnings about ssl certs verification
            "ssl_show_warn": False,
        },
        **connection_params,
    }
    # Enabling basic auth on opensearch client
    # If the user and password are empty we use anonymous auth on opensearch client
    if OPENSEARCH_USER != "" and OPENSEARCH_PASSWORD != "":
        init_params["basic_auth"] = (OPENSEARCH_USER, OPENSEARCH_PASSWORD)
    if host.startswith("https"):
        init_params["use_ssl"] = True
    else:
        init_params["use_ssl"] = False
    if host.startswith("http"):
        url = ""
    else:
        url = "http://"
    url += f"{host}:{OPENSEARCH_PORT}"
    client = OpenSearch(
        url,
        **init_params,
    )
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
