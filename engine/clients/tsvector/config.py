import os

TSVECTOR_PORT = int(os.getenv("TSVECTOR_PORT", 5432))
TSVECTOR_DB = os.getenv("TSVECTOR_DB", "ann")
TSVECTOR_USER = os.getenv("TSVECTOR_USER", "ann")
TSVECTOR_PASSWORD = os.getenv("TSVECTOR_PASSWORD", "ann")


def get_db_config(host, connection_params):
    return {
        "host": host or "localhost",
        "port": TSVECTOR_PORT,
        "dbname": TSVECTOR_DB,
        "user": TSVECTOR_USER,
        "password": TSVECTOR_PASSWORD,
        "autocommit": True,
        **connection_params,
    }
