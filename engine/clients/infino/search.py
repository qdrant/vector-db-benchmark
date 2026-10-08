from dataset_reader.base_reader import Query
from engine.base_client.search import BaseSearcher
from engine.clients.infino.common import BuildConn, resolve_addr
from engine.clients.infino.config import INFINO_QUERY_TIMEOUT_S


class InfinoSearcher(BaseSearcher):
    _host = None
    _port = None
    _ef = 0
    # Per-process socket to the build+serve process (opened lazily per worker).
    _conn: BuildConn | None = None

    @classmethod
    def get_mp_start_method(cls):
        return "spawn"

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        # Runs in the parent and again in every worker; the socket is opened
        # lazily on first search so each worker gets its own connection. Each
        # search_params point carries its own `config.ef`, sent per query so one
        # resident graph is swept across beams (ef=0 serves the stamped curve).
        cls._host, cls._port = resolve_addr(host, connection_params)
        cls._ef = int(search_params.get("config", {}).get("ef", 0) or 0)
        cls._conn = None

    @classmethod
    def search_one(cls, query: Query, top: int) -> list[tuple[int, float]]:
        if cls._conn is None:
            cls._conn = BuildConn(cls._host, cls._port, INFINO_QUERY_TIMEOUT_S)
        ids = cls._conn.search(query.vector, top, cls._ef)
        # Scores are unused (precision is a set intersection of ids); return 0.0.
        return [(i, 0.0) for i in ids]

    @classmethod
    def delete_client(cls):
        if cls._conn is not None:
            cls._conn.close()
            cls._conn = None
