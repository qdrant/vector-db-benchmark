import os
import re

PGVECTOR_PORT = int(os.getenv("PGVECTOR_PORT", 5432))
PGVECTOR_DB = os.getenv("PGVECTOR_DB", "postgres")
PGVECTOR_USER = os.getenv("PGVECTOR_USER", "postgres")
PGVECTOR_PASSWORD = os.getenv("PGVECTOR_PASSWORD", "passwd")

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PAYLOAD_SQL_TYPES = {
    "int": "BIGINT",
    "keyword": "TEXT",
    "text": "TEXT",
    "float": "DOUBLE PRECISION",
    "datetime": "TIMESTAMPTZ",
}

COPY_TYPE_NAMES = {
    "int8": "bigint",
    "int4": "integer",
    "float8": "float8",
    "text": "text",
    "varchar": "text",
    "timestamptz": "timestamptz",
}


def quote_ident(name: str) -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return f'"{name}"'


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
