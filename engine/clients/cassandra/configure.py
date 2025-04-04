from cassandra.cluster import Cluster, ExecutionProfile, EXEC_PROFILE_DEFAULT
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy, ExponentialReconnectionPolicy
from cassandra import ConsistencyLevel, ProtocolVersion

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.cassandra.config import CASSANDRA_KEYSPACE, CASSANDRA_TABLE


class CassandraConfigurator(BaseConfigurator):
    SPARSE_VECTOR_SUPPORT = False
    DISTANCE_MAPPING = {
        Distance.L2: "euclidean",
        Distance.COSINE: "cosine",
        Distance.DOT: "dot_product"
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        
        # Set up execution profiles for consistency and performance
        profile = ExecutionProfile(
            load_balancing_policy=TokenAwarePolicy(DCAwareRoundRobinPolicy()),
            consistency_level=ConsistencyLevel.LOCAL_QUORUM,
            request_timeout=60
        )
        
        # Initialize Cassandra cluster connection
        self.cluster = Cluster(
            contact_points=[host],
            execution_profiles={EXEC_PROFILE_DEFAULT: profile},
            protocol_version=ProtocolVersion.V4,
            reconnection_policy=ExponentialReconnectionPolicy(base_delay=1, max_delay=60),
            **connection_params
        )
        self.session = self.cluster.connect()

    def clean(self):
        """Drop the keyspace if it exists"""
        self.session.execute(f"DROP KEYSPACE IF EXISTS {CASSANDRA_KEYSPACE}")

    def recreate(self, dataset: Dataset, collection_params):
        """Create keyspace and table for vector search"""
        # Create keyspace if not exists
        self.session.execute(
            f"""CREATE KEYSPACE IF NOT EXISTS {CASSANDRA_KEYSPACE} 
            WITH REPLICATION = {{ 'class': 'SimpleStrategy', 'replication_factor': 1 }}"""
        )
        
        # Use the keyspace
        self.session.execute(f"USE {CASSANDRA_KEYSPACE}")
        
        # Get the distance metric
        distance_metric = self.DISTANCE_MAPPING.get(dataset.config.distance)
        vector_size = dataset.config.vector_size
        
        # Create vector table
        # Using a simple schema that supports vector similarity search
        self.session.execute(
            f"""CREATE TABLE IF NOT EXISTS {CASSANDRA_TABLE} (
                id int PRIMARY KEY,
                embedding vector<float, {vector_size}>,
                metadata map<text, text>
            )"""
        )
        
        # Create vector index using the appropriate distance metric
        self.session.execute(
            f"""CREATE CUSTOM INDEX IF NOT EXISTS vector_index ON {CASSANDRA_TABLE}(embedding) 
            USING 'StorageAttachedIndex' 
            WITH OPTIONS = {{ 'similarity_function': '{distance_metric}' }}"""
        )
        
        # Add additional schema fields based on collection_params if needed
        for field_name, field_type in dataset.config.schema.items():
            if field_type in ["keyword", "text"]:
                # For text fields, we would typically add them to metadata
                pass
            elif field_type in ["int", "float"]:
                # For numeric fields that need separate indexing
                # In a real implementation, we might alter the table to add these columns
                pass
        
        return collection_params

    def execution_params(self, distance, vector_size) -> dict:
        """Return any execution parameters needed for the dataset"""
        return {"normalize": distance == Distance.COSINE}

    def delete_client(self):
        """Close the Cassandra connection"""
        if hasattr(self, 'session') and self.session:
            self.session.shutdown()
        if hasattr(self, 'cluster') and self.cluster:
            self.cluster.shutdown()