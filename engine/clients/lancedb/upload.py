from typing import List

import lancedb
from lancedb import DBConnection
from lancedb.table import Table

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.lancedb.config import LANCEDB_COLLECTION_NAME
import pyarrow as pa


class LancedbUploader(BaseUploader):
    client: DBConnection = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        uri = "~/.lancedb"
        cls.client = lancedb.connect(uri, **connection_params)
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        data = [{"vector": point.vector, "id": point.id, **(point.metadata or {})} for point in batch]
        tbl = cls.client.open_table(name=LANCEDB_COLLECTION_NAME)

        i = 15
        while True:
            try:
                tbl.add(data)
            except OSError as e:
                # https://lancedb.github.io/lance/format.html#conflict-resolution
                i -= 1
                if i == 0:
                    raise OSError("After 15 attempts, the conflict could not be resolved.") from e
                continue
            return

    @classmethod
    def get_correct_num_sub_vectors(cls, num_sub_vectors: int, tbl: Table):
        # OSError: Invalid user input: num_sub_vectors must divide vector dimension 100, but got 64
        # Workaround to get dataset.config.vector_size
        field = tbl.schema.field("vector")
        if not pa.types.is_fixed_size_list(field.type):
            return num_sub_vectors
        list_type: pa.FixedSizeListType = field.type
        vector_dimension = list_type.list_size

        def closest_divisor(a, b):
            # Find all divisors of a
            divisors = [i for i in range(1, a + 1) if a % i == 0]
            # Find the divisor closest to b
            closest = min(divisors, key=lambda x: abs(x - b))
            return closest

        return closest_divisor(vector_dimension, num_sub_vectors)

    @classmethod
    def post_upload(cls, _distance):
        # Create and train the index - you need to have enough data in the table for an effective training step
        tbl = cls.client.open_table(name=LANCEDB_COLLECTION_NAME)

        indices = cls.upload_params.get("indices", [])
        for index in indices:
            num_sub_vectors = cls.get_correct_num_sub_vectors(index["num_sub_vectors"], tbl)
            tbl.create_index(num_partitions=index["num_partitions"], num_sub_vectors=num_sub_vectors, metric=_distance)
        return {}
