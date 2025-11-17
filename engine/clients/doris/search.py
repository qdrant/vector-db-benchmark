import atexit
import math
from typing import Dict, List, Tuple

import mysql.connector
from doris_vector_search import AuthOptions, DorisVectorClient
from mysql.connector import ProgrammingError

from dataset_reader.base_reader import Query
from engine.base_client.distances import Distance
from engine.base_client.search import BaseSearcher
from engine.clients.doris.config import (
    DEFAULT_DORIS_DATABASE,
    DEFAULT_DORIS_TABLE,
    DISTANCE_MAPPING,
)


class DorisSearcher(BaseSearcher):
    search_params = {}
    client: DorisVectorClient = None
    table = None
    id_column = "id"
    metric_type = "l2_distance"
    table_name = DEFAULT_DORIS_TABLE
    vector_dim = None
    _cleanup_registered = False

    @classmethod
    def get_mp_start_method(cls):
        return "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        database = (
            search_params.get("database")
            or search_params.get("collection_params", {}).get("database")
            or DEFAULT_DORIS_DATABASE
        )
        auth = AuthOptions(
            host=connection_params.get("host", host),
            query_port=connection_params.get("query_port", 9030),
            http_port=connection_params.get("http_port", 8030),
            user=connection_params.get("user", "root"),
            password=connection_params.get("password", ""),
        )
        # Ensure database exists before connecting
        try:
            tmp_conn = mysql.connector.connect(
                host=auth.host,
                port=auth.query_port,
                user=auth.user,
                password=auth.password,
            )
            cursor = tmp_conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{database}`")
            cursor.close()
            tmp_conn.close()
        except ProgrammingError:
            pass
        cls.client = DorisVectorClient(database=database, auth_options=auth)
        cls.search_params = search_params
        cls.table_name = (
            search_params.get("table_name")
            or search_params.get("collection_params", {}).get("table_name")
            or DEFAULT_DORIS_TABLE
        )
        if isinstance(distance, Distance):
            distance_key = distance.value
        else:
            distance_key = str(distance).lower()
        cls.metric_type = DISTANCE_MAPPING.get(distance_key, "l2_distance")
        cls.vector_dim = search_params.get("vector_dim") or search_params.get(
            "collection_params", {}
        ).get("vector_dim")
        if cls.vector_dim:
            try:
                cls.vector_dim = int(cls.vector_dim)
            except (TypeError, ValueError):
                cls.vector_dim = None

    def setup_search(self):
        if self.__class__.table is None:
            try:
                self.__class__.table = self.__class__.client.open_table(
                    self.__class__.table_name
                )
                if self.__class__.vector_dim:
                    self.__class__.table.index_options.dim = self.__class__.vector_dim
                # Detect id column: first non-vector column from table schema
                # Fallback: "id"
                try:
                    cols = self.__class__.table.column_names
                    # Choose first column that is not vector-like
                    self.__class__.id_column = cols[0] if cols else "id"
                except Exception:
                    pass
                # Apply session overrides for search if provided
                cfg = self.search_params.get("config", {})
                sessions = {}
                # Accept either doris-native key or pgvector-like alias
                if "hnsw_ef_search" in cfg:
                    sessions["hnsw_ef_search"] = str(cfg["hnsw_ef_search"])
                if "hnsw_ef" in cfg and "hnsw_ef_search" not in sessions:
                    sessions["hnsw_ef_search"] = str(cfg["hnsw_ef"])
                if sessions:
                    try:
                        self.__class__.client.with_sessions(sessions)
                    except Exception:
                        pass
            except Exception as ex:
                raise RuntimeError(
                    f"Failed to open Doris table '{self.__class__.table_name}': {ex}"
                )

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        if cls.table is None:
            cls.table = cls.client.open_table(cls.table_name)
            if cls.vector_dim:
                cls.table.index_options.dim = cls.vector_dim
        vector_query = cls.table.search(query.vector, metric_type=cls.metric_type)
        vector_query.limit(top)

        res = cls._execute_vector_query(vector_query)
        results = []
        for row in res:
            # Distance field may vary; try common keys
            distance = row.get("distance") or row.get("score") or 0.0
            identifier = row.get(cls.id_column) or row.get("id")
            if identifier is None:
                continue
            try:
                identifier = int(identifier)
            except Exception:
                # If cannot cast, skip
                continue
            results.append((identifier, float(distance)))
        return results

    @classmethod
    def _execute_vector_query(cls, vector_query) -> List[Dict[str, object]]:
        select_columns = (
            vector_query.selected_columns or vector_query.table.column_names
        )
        distance_range = None
        if (
            vector_query.distance_range_lower is not None
            or vector_query.distance_range_upper is not None
        ):
            distance_range = (
                vector_query.distance_range_lower,
                vector_query.distance_range_upper,
            )

        where_conditions = vector_query.where_conditions or None

        sql = vector_query.compiler.compile_vector_search_query(
            table_name=vector_query.table.table_name,
            query_vector=vector_query.query_vector,
            vector_column=vector_query.vector_column,
            limit=vector_query.limit_value,
            distance_range=distance_range,
            where_conditions=where_conditions,
            selected_columns=select_columns,
            metric_type=vector_query.metric_type,
        )

        cursor = vector_query.table._get_cursor(prepared=False)
        cursor.execute(sql)
        rows = cursor.fetchall() or []

        processed: List[Dict[str, object]] = []
        for raw_row in rows:
            row_dict: Dict[str, object] = {}
            for col_name, value in zip(select_columns, raw_row):
                if isinstance(value, (bytes, bytearray)):
                    value = value.decode("utf-8")
                row_dict[col_name] = value

            processed.append(
                cls._postprocess_row(
                    row_dict,
                    vector_query.vector_column,
                    vector_query.query_vector,
                )
            )

        return processed

    @classmethod
    def _postprocess_row(
        cls,
        row: Dict[str, object],
        vector_column: str,
        query_vector: List[float],
    ) -> Dict[str, object]:
        vector_data = row.get(vector_column)

        if (
            isinstance(vector_data, str)
            and vector_data.startswith("[")
            and vector_data.endswith("]")
        ):
            try:
                vector_values = [
                    float(item.strip())
                    for item in vector_data[1:-1].split(",")
                    if item.strip()
                ]
            except ValueError:
                vector_values = None
            else:
                row[vector_column] = vector_values
        elif isinstance(vector_data, list):
            vector_values = vector_data
        else:
            vector_values = None

        if vector_values and len(vector_values) == len(query_vector):
            if cls.metric_type == "inner_product":
                score = sum(a * b for a, b in zip(query_vector, vector_values))
                row.setdefault("score", score)
                row.setdefault("distance", -score)
            else:
                dist_sq = sum((a - b) ** 2 for a, b in zip(query_vector, vector_values))
                row.setdefault("distance", math.sqrt(dist_sq))

        return row

    @classmethod
    def delete_client(cls):
        try:
            if cls.client:
                cls.client.close()
        finally:
            cls.client = None
            cls.table = None


if not DorisSearcher._cleanup_registered:
    atexit.register(DorisSearcher.delete_client)
    DorisSearcher._cleanup_registered = True
