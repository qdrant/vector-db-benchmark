DEFAULT_DORIS_DATABASE = "benchmark"
DEFAULT_DORIS_TABLE = "vectors"

# Mapping from internal distances to doris metric_type
DISTANCE_MAPPING = {
    "l2": "l2_distance",
    "dot": "inner_product",
    # Cosine can be approximated by inner product if vectors normalized upstream
    "cosine": "inner_product",
}