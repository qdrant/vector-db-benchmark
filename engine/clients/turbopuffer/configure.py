import turbopuffer as tpuf

import engine.clients.turbopuffer.config as tpuf_config
from benchmark.dataset import Dataset
from engine.base_client.configure import BaseConfigurator
from engine.base_client.distances import Distance
from engine.clients.turbopuffer.config import (
    TURBOPUFFER_API_KEY,
    TURBOPUFFER_REGION,
    resolve_namespace,
)


class TurbopufferConfigurator(BaseConfigurator):
    DISTANCE_MAPPING = {
        Distance.COSINE: "cosine_distance",
        Distance.L2: "euclidean_squared",
    }

    def __init__(self, host, collection_params: dict, connection_params: dict):
        super().__init__(host, collection_params, connection_params)
        api_key = connection_params.get("api_key", TURBOPUFFER_API_KEY)
        region = connection_params.get("region", TURBOPUFFER_REGION)
        self.client = tpuf.Turbopuffer(api_key=api_key, region=region)

    def configure(self, dataset: Dataset):
        # Resolve namespace (explicit > env > dataset name) and publish for
        # uploader/searcher instances that share this process or are spawned after.
        tpuf_config._active_namespace = resolve_namespace(
            self.connection_params, dataset_name=dataset.config.name
        )
        return super().configure(dataset)

    def clean(self):
        ns = self.client.namespace(tpuf_config._active_namespace)
        if ns.exists():
            ns.delete_all()

    def recreate(self, dataset: Dataset, collection_params):
        pass
