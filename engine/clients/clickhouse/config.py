from engine.base_client.distances import Distance

CLICKHOUSE_PORT = 8123
CLICKHOUSE_DATABASE = "default"
CLICKHOUSE_TABLE = "bench"
CLICKHOUSE_USER = "default"
CLICKHOUSE_PASSWORD = "passwd"
DISTANCE_MAPPING = {
    Distance.L2: "L2Distance",
    Distance.COSINE: "cosineDistance",
    Distance.DOT: "dotProduct",
}