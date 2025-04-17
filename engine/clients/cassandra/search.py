import multiprocessing as mp
from typing import List, Tuple

from cassandra import ConsistencyLevel, ProtocolVersion
from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile
from cassandra.policies import (
    DCAwareRoundRobinPolicy,
    ExponentialReconnectionPolicy,
    TokenAwarePolicy,
)

from dataset_reader.base_reader import Query
from engine.base_client.distances import Distance
from engine.base_client.search import BaseSearcher
from engine.clients.cassandra.config import CASSANDRA_KEYSPACE, CASSANDRA_TABLE
from engine.clients.cassandra.parser import CassandraConditionParser


class CassandraSearcher(BaseSearcher):
    search_params = {}
    session = None
    cluster = None
    parser = CassandraConditionParser()

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        # Set up execution profiles for consistency and performance
        profile = ExecutionProfile(
            load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy()),
            consistency_level=ConsistencyLevel.LOCAL_ONE,
            request_timeout=60,
        )

        # Initialize Cassandra cluster connection
        cls.cluster = Cluster(
            contact_points=[host],
            execution_profiles={EXEC_PROFILE_DEFAULT: profile},
            reconnection_policy=ExponentialReconnectionPolicy(
                base_delay=1, max_delay=60
            ),
            protocol_version=ProtocolVersion.V4,
            **connection_params,
        )
        cls.session = cls.cluster.connect(CASSANDRA_KEYSPACE)
        cls.search_params = search_params

        # Update prepared statements with current search parameters
        cls.update_prepared_statements(distance)

    @classmethod
    def get_mp_start_method(cls):
        return "fork" if "fork" in mp.get_all_start_methods() else "spawn"

    @classmethod
    def update_prepared_statements(cls, distance):
        """Create prepared statements for vector searches"""
        # Prepare a vector similarity search query
        limit = cls.search_params.get("top", 10)

        if distance == Distance.COSINE:
            SIMILARITY_FUNC = "similarity_cosine"
        elif distance == Distance.L2:
            SIMILARITY_FUNC = "similarity_euclidean"
        elif distance == Distance.DOT:
            SIMILARITY_FUNC = "similarity_dot_product"
        else:
            raise ValueError(f"Unsupported distance metric: {distance}")

        cls.ann_search_stmt = cls.session.prepare(
            f"""SELECT id, {SIMILARITY_FUNC}(embedding, ?) as distance
            FROM {CASSANDRA_TABLE}
            ORDER BY embedding ANN OF ?
            LIMIT {limit}"""
        )

        # Prepare a statement for filtered vector search
        cls.filtered_search_query_template = f"""SELECT id, {SIMILARITY_FUNC}(embedding, ?) as distance
            FROM {CASSANDRA_TABLE}
            WHERE {{conditions}}
            ORDER BY embedding ANN OF ?
            LIMIT {limit}"""

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        """Execute a vector similarity search with optional filters"""
        # Convert query vector to a format Cassandra can use
        query_vector = (
            query.vector.tolist() if hasattr(query.vector, "tolist") else query.vector
        )

        # Generate filter conditions if metadata conditions exist
        filter_conditions = cls.parser.parse(query.meta_conditions)

        try:
            if filter_conditions:
                # Use the filtered search query
                query_with_conditions = cls.filtered_search_query_template.format(
                    conditions=filter_conditions
                )
                results = cls.session.execute(
                    cls.session.prepare(query_with_conditions),
                    (query_vector, query_vector),
                )
            else:
                # Use the basic ANN search query
                results = cls.session.execute(
                    cls.ann_search_stmt, (query_vector, query_vector)
                )

            # Extract and return results
            return [(row.id, row.distance) for row in results]

        except Exception as ex:
            print(f"Error during Cassandra vector search: {ex}")
            raise ex

    @classmethod
    def delete_client(cls):
        """Close the Cassandra connection"""
        if cls.session:
            cls.session.shutdown()
        if cls.cluster:
            cls.cluster.shutdown()
