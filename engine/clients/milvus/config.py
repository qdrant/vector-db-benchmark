from engine.base_client.distances import Distance

MILVUS_COLLECTION_NAME = "Benchmark"
MILVUS_DEFAULT_ALIAS = "bench"
MILVUS_DEFAULT_PORT = "19530"

DISTANCE_MAPPING = {
    Distance.L2: "L2",
    Distance.DOT: "IP",
    # Milvus does not support cosine. Cosine is equal to IP of normalized vectors
    Distance.COSINE: "IP"
    # Jaccard, Tanimoto, Hamming distance, Superstructure and Substructure are also available
}
