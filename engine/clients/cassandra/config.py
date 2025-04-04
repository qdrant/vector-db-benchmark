import os

CASSANDRA_KEYSPACE = os.getenv("CASSANDRA_KEYSPACE", "benchmark")
CASSANDRA_TABLE = os.getenv("CASSANDRA_TABLE", "vectors")
ASTRA_API_ENDPOINT = os.getenv("ASTRA_API_ENDPOINT", None)
ASTRA_API_KEY = os.getenv("ASTRA_API_KEY", None)
ASTRA_SCB_PATH = os.getenv("ASTRA_SCB_PATH", None)