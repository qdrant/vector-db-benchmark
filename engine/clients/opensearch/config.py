import os

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
        },
        **connection_params,
    }
    if host.startswith("http"):
        url = ""
    else:
        url = "http://"
    url += f"{host}:{OPENSEARCH_PORT}"

    client = OpenSearch(
        f"http://{host}:{OPENSEARCH_PORT}",
        basic_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
        **init_params,
    )
    assert client.ping()
    return client
