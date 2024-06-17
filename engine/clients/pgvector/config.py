import os

PGVECTOR_PORT = int(os.getenv("PGVECTOR_PORT", 5432))
PGVECTOR_DB = os.getenv("PGVECTOR_DB", "postgres")
PGVECTOR_USER = os.getenv("PGVECTOR_USER", "postgres")
PGVECTOR_PASSWORD = os.getenv("PGVECTOR_PASSWORD", "passwd")


def get_db_config(host, connection_params):
    return {
        "host": host or "localhost",
        "port": PGVECTOR_PORT,
        "dbname": PGVECTOR_DB,
        "user": PGVECTOR_USER,
        "password": PGVECTOR_PASSWORD,
        "autocommit": True,
        **connection_params,
    }
