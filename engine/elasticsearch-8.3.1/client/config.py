import os

ELASTIC_HOST = os.environ.get("SERVER_HOST", "elastic_server")
ELASTIC_PORT = 9200
ELASTIC_INDEX = "bench"
ELASTIC_USER = "elastic"
ELASTIC_PASSWORD = "passwd"
