from pymilvus import DataType, connections
import os
from engine.base_client.distances import Distance

MILVUS_COLLECTION_NAME = "Benchmark"
MILVUS_DEFAULT_ALIAS = "bench"
MILVUS_DEFAULT_PORT = "19530"
MILVUS_PASS = os.getenv("MILVUS_PASS", "")
MILVUS_USER = os.getenv("MILVUS_USER", "")
MILVUS_PORT = os.getenv("MILVUS_PORT", MILVUS_DEFAULT_PORT)

DISTANCE_MAPPING = {
    Distance.L2: "L2",
    Distance.DOT: "IP",
    # Milvus does not support cosine. Cosine is equal to IP of normalized vectors
    Distance.COSINE: "IP",
    # Jaccard, Tanimoto, Hamming distance, Superstructure and Substructure are also available
}

DTYPE_EXTRAS = {
    "keyword": {"max_length": 500},
    "text": {"max_length": 5000},
}

DTYPE_DEFAULT = {
    DataType.INT64: 0,
    DataType.VARCHAR: "---MILVUS DOES NOT ACCEPT EMPTY STRINGS---",
    DataType.FLOAT: 0.0,
}


def get_milvus_client(connection_params: dict, host: str, alias: str):
    h = ""
    uri = ""
    if host.startswith("http"):
        uri = host
    else:
        h = host
    client = connections.connect(
        alias=alias,
        host=h,
        uri=uri,
        port=MILVUS_PORT,
        user=MILVUS_USER,
        password=MILVUS_PASS,
        **connection_params
    )
    return client
