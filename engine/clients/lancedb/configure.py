import lancedb
import pyarrow as pa

from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.lancedb.config import LANCEDB_COLLECTION_NAME


class LancedbConfigurator(BaseConfigurator):

    DISTANCE_MAPPING = {
        Distance.L2: "l2",
        Distance.COSINE: "cosine",
        Distance.DOT: "dot",
    }

    DTYPE_MAPPING = {
        "int": pa.int64(),
        "keyword": pa.string(),
        "text": pa.string(),
        "float": pa.float32(),
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        uri = "~/.lancedb"
        self.client = lancedb.connect(uri, **connection_params)

    def clean(self):
        """
        Delete a collection and all associated embeddings, documents, and metadata.

        This is destructive and not reversible.
        """
        try:
            self.client.drop_table(LANCEDB_COLLECTION_NAME)
        except (Exception, ValueError):
            pass

    def recreate(self, dataset: Dataset, collection_params):
        schema = pa.schema([
            pa.field("vector", pa.list_(pa.float32(), list_size=dataset.config.vector_size)),
            pa.field("id", pa.int64()),
        ] + [
            pa.field(field_name, self.DTYPE_MAPPING.get(field_type))
            for field_name, field_type in dataset.config.schema.items()
        ])
        self.client.create_table(name=LANCEDB_COLLECTION_NAME, schema=schema)
