import atexit
from contextlib import closing
from typing import List

from doris_vector_search import DorisVectorClient, AuthOptions, IndexOptions
import mysql.connector
from mysql.connector import ProgrammingError, Error

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.doris.config import (
    DEFAULT_DORIS_DATABASE,
    DEFAULT_DORIS_TABLE,
)


class DorisUploader(BaseUploader):
    client: DorisVectorClient = None
    table = None
    created = False
    upload_params = {}
    collection_params = {}
    metric_type = "l2_distance"
    vector_dim = None
    _cleanup_registered = False

    @classmethod
    def get_mp_start_method(cls):
        return "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        # Prefer database passed within collection_params (from experiment file)
        database = (
            upload_params.get("database")
            or upload_params.get("collection_params", {}).get("database")
            or DEFAULT_DORIS_DATABASE
        )
        auth = AuthOptions(
            host=connection_params.get("host", host),
            query_port=connection_params.get("query_port", 9030),
            http_port=connection_params.get("http_port", 8030),
            user=connection_params.get("user", "root"),
            password=connection_params.get("password", ""),
        )
        # Ensure database exists
        try:
            with closing(
                mysql.connector.connect(
                    host=auth.host,
                    port=auth.query_port,
                    user=auth.user,
                    password=auth.password,
                )
            ) as tmp_conn:
                with closing(tmp_conn.cursor()) as cursor:
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
        except ProgrammingError:
            pass

        cls.upload_params = upload_params
        cls.collection_params = upload_params.get("collection_params", {})
        cls.vector_dim = (
            upload_params.get("vector_dim")
            or cls.collection_params.get("vector_dim")
        )
        if cls.vector_dim:
            try:
                cls.vector_dim = int(cls.vector_dim)
            except (TypeError, ValueError):
                cls.vector_dim = None
        # Map distance to Doris metric type
        from engine.clients.doris.config import DISTANCE_MAPPING as _MAP
        # distance can be Distance enum or string
        if hasattr(distance, "value"):
            cls.metric_type = _MAP.get(distance.value, "l2_distance")
        else:
            cls.metric_type = _MAP.get(str(distance), "l2_distance")

        if cls.client is not None:
            return

        cls.client = DorisVectorClient(database=database, auth_options=auth)

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        rows = []
        for rec in batch:
            row = {"id": rec.id, "vector": rec.vector}
            if rec.metadata:
                for k, v in rec.metadata.items():
                    # Avoid overwriting existing keys
                    if k not in row:
                        row[k] = v
            rows.append(row)

        table_name = cls.collection_params.get("table_name", DEFAULT_DORIS_TABLE)
        # Allow overriding table name from upload_params root
        table_name = cls.upload_params.get("table_name", table_name)

        if not cls.created:
            table_exists = cls._table_exists(table_name)
            if table_exists:
                cls.table = cls.client.open_table(table_name)
            else:
                # Table does not exist (yet), attempt to create using the first batch
                hnsw_cfg = cls.upload_params.get("hnsw_config", {})
                index_options = IndexOptions(
                    metric_type=cls.metric_type,
                    max_degree=hnsw_cfg.get("m", 32),
                    ef_construction=hnsw_cfg.get("ef_construct", 40),
                    dim=cls.vector_dim if cls.vector_dim else -1,
                )
                try:
                    cls.table = cls.client.create_table(
                        table_name,
                        rows,
                        create_index=True,
                        index_options=index_options,
                        overwrite=False,
                    )
                except Error as exc:
                    # If table already created by another process, just open it
                    if "already exists" in str(exc).lower():
                        cls.table = cls.client.open_table(table_name)
                    else:
                        raise
            cls.created = True

        if cls.table is None:
            cls.table = cls.client.open_table(table_name)
        if cls.vector_dim and cls.table:
            cls.table.index_options.dim = cls.vector_dim
        cls.table.add(rows)

    @classmethod
    def post_upload(cls, _distance):
        return {}

    @classmethod
    def _table_exists(cls, table_name: str) -> bool:
        if cls.client is None:
            return False
        try:
            cursor = cls.client.connection.cursor()
            try:
                cursor.execute("SHOW TABLES LIKE %s", (table_name,))
                return cursor.fetchone() is not None
            finally:
                cursor.close()
        except Exception:
            return False

    @classmethod
    def delete_client(cls):
        try:
            if cls.client:
                cls.client.close()
        finally:
            cls.client = None
            cls.table = None
            cls.created = False


# Register cleanup once per interpreter to silence resource warnings when using pools
if not DorisUploader._cleanup_registered:
    atexit.register(DorisUploader.delete_client)
    DorisUploader._cleanup_registered = True