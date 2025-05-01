import time
from typing import List

from cassandra import ConsistencyLevel, ProtocolVersion
from cassandra.cluster import EXEC_PROFILE_DEFAULT, Cluster, ExecutionProfile, ResultSet
from cassandra.policies import (
    DCAwareRoundRobinPolicy,
    ExponentialReconnectionPolicy,
    TokenAwarePolicy,
)

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.cassandra.config import CASSANDRA_KEYSPACE, CASSANDRA_TABLE


class CassandraUploader(BaseUploader):
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        # Set up execution profiles for consistency and performance
        profile = ExecutionProfile(
            load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy()),
            consistency_level=ConsistencyLevel.LOCAL_QUORUM,
            request_timeout=60,
        )

        # Initialize Cassandra cluster connection
        cls.cluster = Cluster(
            contact_points=[host],
            execution_profiles={EXEC_PROFILE_DEFAULT: profile},
            protocol_version=ProtocolVersion.V4,
            reconnection_policy=ExponentialReconnectionPolicy(
                base_delay=1, max_delay=60
            ),
            **connection_params,
        )
        cls.session = cls.cluster.connect(CASSANDRA_KEYSPACE)
        cls.upload_params = upload_params

        # Prepare statements for faster uploads
        cls.insert_stmt = cls.session.prepare(
            f"""INSERT INTO {CASSANDRA_TABLE} (id, embedding, metadata) VALUES (?, ?, ?)"""
        )

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        """Upload a batch of records to Cassandra"""
        for point in batch:
            # Convert metadata to a map format that Cassandra can store
            metadata = {}
            if point.metadata:
                for key, value in point.metadata.items():
                    # Convert all values to strings for simplicity
                    metadata[str(key)] = str(value)

            # Cassandra vector type requires a list of float values
            vector = (
                point.vector.tolist()
                if hasattr(point.vector, "tolist")
                else point.vector
            )

            # Execute the prepared statement
            cls.session.execute(cls.insert_stmt, (int(point.id), vector, metadata))

    @classmethod
    def check_index_status(cls) -> ResultSet:
        """
        Check the status of the index
        See https://docs.datastax.com/en/cql/cassandra-5.0/develop/indexing/sai/sai-monitor.html
        """
        if cls.session is None:
            raise RuntimeError("CQL session is not initialized")
        return cls.session.execute(
            f"""
            SELECT is_queryable, is_building
            FROM system_views.sai_column_indexes
            WHERE keyspace_name='{CASSANDRA_KEYSPACE}' AND table_name='{CASSANDRA_TABLE}' AND index_name='vector_index';
            """
        ).one()

    @classmethod
    def post_upload(cls, _distance):
        """Post-upload operations, like waiting for indexing to complete"""
        # Cassandra vector indexes are automatically built when data is inserted
        # so the wait time must be very quick
        while True:
            result = cls.check_index_status()
            idx_ready = result and result.is_queryable and not result.is_building
            if idx_ready:
                break
            print("Index is not ready yet, sleeping for 30 seconds...")
            time.sleep(30)
        return {}

    @classmethod
    def delete_client(cls):
        """Close the Cassandra connection"""
        if hasattr(cls, "session") and cls.session:
            cls.session.shutdown()
        if hasattr(cls, "cluster") and cls.cluster:
            cls.cluster.shutdown()
