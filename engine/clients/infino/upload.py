import numpy as np

from dataset_reader.base_reader import Record
from engine.base_client.upload import BaseUploader
from engine.clients.infino.common import BuildConn, resolve_addr
from engine.clients.infino.config import INFINO_BUILD_TIMEOUT_S


class InfinoUploader(BaseUploader):
    conn: BuildConn = None
    _host = None
    _port = None

    @classmethod
    def get_mp_start_method(cls):
        return "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, upload_params: dict):
        # Upload must stay single-worker: appends share one server table whose
        # handle is not multi-writer, and interleaving batches across sockets
        # would make row order nondeterministic. Enforce it rather than trust
        # the config (a pool would also leak a socket per worker).
        if int(upload_params.get("parallel", 1)) != 1:
            raise ValueError("Infino upload requires upload_params.parallel = 1")
        cls._host, cls._port = resolve_addr(host, connection_params)
        cls.conn = BuildConn(cls._host, cls._port, INFINO_BUILD_TIMEOUT_S)

    @classmethod
    def upload_batch(cls, batch: list[Record]):
        if not batch:
            return
        ids = [r.id for r in batch]
        vectors = np.asarray([r.vector for r in batch], dtype=np.float32)
        cls.conn.append(ids, vectors)

    @classmethod
    def post_upload(cls, distance):
        # Drain + build the serving index (hnsw_ivf builds the resident graph)
        # and the server-side _id -> dataset-id map.
        cls.conn.optimize()
        return {}

    @classmethod
    def delete_client(cls):
        if cls.conn is not None:
            cls.conn.close()
            cls.conn = None
