from typing import List

import numpy as np
import clickhouse_connect
from clickhouse_connect.datatypes.container import Array
from clickhouse_connect.datatypes.numeric import Float64, UInt64

from dataset_reader.base_reader import Record
from engine.base_client import IncompatibilityError
from engine.base_client.distances import Distance
from engine.base_client.upload import BaseUploader
from engine.clients.clickhouse.config import get_db_config


class CHVectorUploader(BaseUploader):
    DISTANCE_MAPPING = {
        Distance.L2: "vector_l2_ops",
        Distance.COSINE: "vector_cosine_ops",
    }
    client = None
    upload_params = {}

    @classmethod
    def init_client(cls, host, distance, connection_params, upload_params):
        cls.client = clickhouse_connect.driver.create_client(**get_db_config(connection_params))
        cls.upload_params = upload_params

    @classmethod
    def upload_batch(cls, batch: List[Record]):
        ids, vectors = [], []
        for record in batch:
            ids.append(record.id)
            vectors.append(record.vector)
        #array_vectors = np.array(vectors)
        both_columns = [ids, vectors]


        cls.client.insert(table='items', data=both_columns,
                          column_names=['id', 'embedding'],
                          column_type_names=['UInt64', 'Array(Float64)'], column_oriented=True)
        #print(query_summary)
        #return query_summary

    @classmethod
    def post_upload(cls, distance):
        try:
            hnsw_distance_type = cls.DISTANCE_MAPPING[distance]
        except KeyError:
            raise IncompatibilityError(f"Unsupported distance metric: {distance}")

        #cls.conn.execute(
        #    f"CREATE INDEX ON items USING hnsw (embedding {hnsw_distance_type}) WITH (m = {cls.upload_params['hnsw_config']['m']}, ef_construction = {cls.upload_params['hnsw_config']['ef_construct']})"
        #)
        return {}

    @classmethod
    def delete_client(cls):
        cls.client.close()

