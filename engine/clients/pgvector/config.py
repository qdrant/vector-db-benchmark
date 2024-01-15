PGVECTOR_PORT = 9200
PGVECTOR_DB = "postgres"
PGVECTOR_USER = "postgres"
PGVECTOR_PASSWORD = "passwd"


def get_db_config(host, connection_params):
    return {
        "host": host or "localhost",
        "dbname": PGVECTOR_DB,
        "user": PGVECTOR_USER,
        "password": PGVECTOR_PASSWORD,
        "autocommit": True,
        **connection_params,
    }
