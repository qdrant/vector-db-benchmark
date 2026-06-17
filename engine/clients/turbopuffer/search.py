import threading
from typing import List, Tuple

import turbopuffer as tpuf

import engine.clients.turbopuffer.config as tpuf_config
from dataset_reader.base_reader import Query
from engine.base_client.search import BaseSearcher
from engine.clients.turbopuffer.config import (
    TURBOPUFFER_API_KEY,
    TURBOPUFFER_REGION,
    resolve_namespace,
)

CACHE_STRATEGY_HINT_WARM = "hint_warm"
CACHE_STRATEGY_PINNED = "pinned"


class TurbopufferSearcher(BaseSearcher):
    client: tpuf.Turbopuffer = None
    namespace = None  # Namespace type, used when namespace_field is not set
    namespaces: dict = {}  # tenant_value -> Namespace, used when namespace_field is set
    base_namespace: str = None
    namespace_field: str = None
    search_params = {}
    _utilization_stop = None

    @classmethod
    def get_mp_start_method(cls):
        return "spawn"

    def _start_utilization_poller(self, interval=30):
        stop = threading.Event()
        self.__class__._utilization_stop = stop

        def poll():
            while not stop.wait(interval):
                try:
                    meta = self.__class__.namespace.metadata()
                    util = meta.pinning.status.utilization if (meta.pinning and meta.pinning.status) else None
                    ready = meta.pinning.status.ready_replicas if (meta.pinning and meta.pinning.status) else None
                    print(f"Turbopuffer utilization: {util} (ready_replicas={ready})", flush=True)
                except Exception as e:
                    print(f"Turbopuffer utilization poll error: {e}", flush=True)

        t = threading.Thread(target=poll, daemon=True)
        t.start()

    def setup_search(self):
        if "namespace" not in self.connection_params and tpuf_config._active_namespace:
            self.connection_params["namespace"] = tpuf_config._active_namespace

        strategy = self.search_params.get("cache_strategy")
        if strategy == CACHE_STRATEGY_HINT_WARM:
            print("Turbopuffer: sending hint_cache_warm...")
            self.__class__.namespace.hint_cache_warm()
            print("Turbopuffer: cache warm hint accepted")
        elif strategy == CACHE_STRATEGY_PINNED:
            import time as _time
            replicas = self.search_params.get("pinned_replicas", 1)
            print(f"Turbopuffer: pinning namespace (replicas={replicas})...")
            self.__class__.namespace.update_metadata(pinning={"replicas": replicas})
            print("Turbopuffer: waiting for pinning to be ready...")
            while True:
                meta = self.__class__.namespace.metadata()
                ready = meta.pinning.status.ready_replicas if (meta.pinning and meta.pinning.status) else 0
                utilization = meta.pinning.status.utilization if (meta.pinning and meta.pinning.status) else None
                print(f"Turbopuffer: ready_replicas={ready}/{replicas} utilization={utilization}")
                if ready >= replicas:
                    break
                _time.sleep(10)
            print("Turbopuffer: namespace pinned and ready")
            self._start_utilization_poller(interval=30)

    def post_search(self):
        if self.__class__._utilization_stop:
            self.__class__._utilization_stop.set()
            self.__class__._utilization_stop = None

        strategy = self.search_params.get("cache_strategy")
        if strategy == CACHE_STRATEGY_PINNED:
            print("Turbopuffer: unpinning namespace...")
            self.__class__.namespace.update_metadata(pinning=None)
            print("Turbopuffer: namespace unpinned")

    @classmethod
    def init_client(cls, host, distance, connection_params: dict, search_params: dict):
        api_key = connection_params.get("api_key", TURBOPUFFER_API_KEY)
        region = connection_params.get("region", TURBOPUFFER_REGION)
        cls.client = tpuf.Turbopuffer(api_key=api_key, region=region)
        cls.namespace_field = connection_params.get("namespace_field")
        cls.base_namespace = resolve_namespace(connection_params)
        cls.namespaces = {}
        if cls.namespace_field:
            cls.namespace = None
        else:
            cls.namespace = cls.client.namespace(cls.base_namespace)
        cls.search_params = search_params

    @classmethod
    def _get_tenant_namespace(cls, tenant_value: str):
        if tenant_value not in cls.namespaces:
            cls.namespaces[tenant_value] = cls.client.namespace(
                f"{cls.base_namespace}-{tenant_value}"
            )
        return cls.namespaces[tenant_value]

    @classmethod
    def _extract_tenant_value(cls, meta_conditions: dict):
        """Extract the namespace_field value from meta_conditions for namespace routing."""
        field = cls.namespace_field

        def search_clause(clause):
            for k, v in clause.items():
                if k in ("and", "must"):
                    for sub in v:
                        result = search_clause(sub)
                        if result is not None:
                            return result
                elif k == field:
                    match = v.get("match", {})
                    if "value" in match:
                        return str(match["value"])
            return None

        return search_clause(meta_conditions)

    @classmethod
    def _translate_filter(cls, conditions: dict):
        """Translate Qdrant-style filter conditions to turbopuffer tuple filter format."""
        if not conditions:
            return None

        def translate_clause(clause: dict):
            for field, cond in clause.items():
                if field in ("and", "or", "must", "should"):
                    op = "And" if field in ("and", "must") else "Or"
                    return (op, [translate_clause(c) for c in cond])
                if field == "must_not":
                    return ("Not", ("Or", [translate_clause(c) for c in cond]))
                # leaf: {"field": {"match": {"value": v}}} or {"field": {"match": {"any": [...]}}}
                match = cond.get("match")
                if match is not None:
                    if "value" in match:
                        return (field, "Eq", match["value"])
                    if "any" in match:
                        return (field, "In", match["any"])
                rng = cond.get("range")
                if rng is not None:
                    clauses = []
                    if "gt" in rng:
                        clauses.append((field, "Gt", rng["gt"]))
                    if "gte" in rng:
                        clauses.append((field, "Gte", rng["gte"]))
                    if "lt" in rng:
                        clauses.append((field, "Lt", rng["lt"]))
                    if "lte" in rng:
                        clauses.append((field, "Lte", rng["lte"]))
                    return ("And", clauses) if len(clauses) > 1 else clauses[0]
            raise ValueError(f"Unsupported filter clause: {clause}")

        return translate_clause(conditions)

    @classmethod
    def search_one(cls, query: Query, top: int) -> List[Tuple[int, float]]:
        try:
            if cls.namespace_field:
                # Route to per-tenant namespace, no filter needed
                tenant = cls._extract_tenant_value(query.meta_conditions)
                if tenant is None:
                    raise ValueError(f"Could not extract '{cls.namespace_field}' from meta_conditions")
                ns = cls._get_tenant_namespace(tenant)
                result = ns.query(
                    rank_by=("vector", "ANN", query.vector),
                    top_k=top,
                    include_attributes=False,
                )
            else:
                extra = {}
                if query.meta_conditions:
                    extra["filters"] = cls._translate_filter(query.meta_conditions)
                result = cls.namespace.query(
                    rank_by=("vector", "ANN", query.vector),
                    top_k=top,
                    include_attributes=False,
                    **extra,
                )
            return [(int(row.id), row["$dist"]) for row in result.rows]
        except Exception as ex:
            raise RuntimeError(f"{type(ex).__name__}: {ex}") from None

    @classmethod
    def delete_client(cls):
        cls.client = None
        cls.namespace = None
        cls.namespaces = {}
