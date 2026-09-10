from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.infino.common import BuildConn, resolve_addr
from engine.clients.infino.config import DISTANCE_MAPPING as _DM
from engine.clients.infino.config import INFINO_BUILD_TIMEOUT_S


class InfinoConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = _DM

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        self._host, self._port = resolve_addr(host, connection_params)

    def clean(self):
        # CREATE drops any existing table first, so a separate clean only resets
        # the server between unrelated runs. Let a connection failure surface (a
        # bad --host should fail here, not silently later); only tolerate the
        # server reporting there is no such table to drop.
        conn = BuildConn(self._host, self._port, INFINO_BUILD_TIMEOUT_S)
        try:
            conn.drop()
        except RuntimeError:
            pass  # no existing table — nothing to reset
        finally:
            conn.close()

    def recreate(self, dataset: Dataset, collection_params):
        dim = dataset.config.vector_size
        metric = self.DISTANCE_MAPPING[dataset.config.distance]
        conn = BuildConn(self._host, self._port, INFINO_BUILD_TIMEOUT_S)
        try:
            conn.create(dim, metric)
        finally:
            conn.close()

    def execution_params(self, distance, vector_size) -> dict:
        # Infino's cosine codec uses a fixed [-1, 1] grid, so cosine input must
        # be unit-normalized. The reader normalizes both base + query vectors.
        return {"normalize": distance == Distance.COSINE}
