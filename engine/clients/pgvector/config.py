
from engine.base_client.distances import Distance

PGVECTOR_TABLE_NAME = "Benchmark_deep_image"
PGVECTOR_DATABASE_NAME = "test"
PGVECTOR_USER = "test_app"
PGVECTOR_PASSWORD = "yvsjMfGg"
PGVECTOR_PORT = "5432" 

DISTANCE_INDEX_MAPPING = {
    Distance.L2: "vector_l2_ops",
    Distance.DOT: "vector_ip_ops",
    Distance.COSINE: "vector_cosine_ops"
}
DISTANCE_QUERY_MAPPING = {
    Distance.L2: "embedding <->",
    Distance.DOT: "-1 * (embedding <#>",
    Distance.COSINE: "1 - (embedding <=>"
}
DISTANCE_QUERY_MAPPING_END = {
    Distance.L2: "",
    Distance.DOT: ")",
    Distance.COSINE: ")"
}
DISTANCE_MAPPING = {
    Distance.L2: "<->",
    Distance.DOT: "<#>",
    Distance.COSINE: "<=>"
}
FIELD_MAPPING = {
        "int": "integer",
        "keyword": "varchar",
        "text": "text",
        "float": "real",
        "geo": "point",
}

def get_pgvector_connection_string(host):
    return f"dbname={PGVECTOR_DATABASE_NAME} user={PGVECTOR_USER} password={PGVECTOR_PASSWORD} host={host} port={PGVECTOR_PORT}"