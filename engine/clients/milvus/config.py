from pymilvus import DataType

from engine.base_client.distances import Distance

MILVUS_COLLECTION_NAME = "Benchmark"
MILVUS_DEFAULT_ALIAS = "bench"
MILVUS_DEFAULT_PORT = "19530"

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
    DataType.DOUBLE: 0.0,
}
