import os

from engine.base_client.distances import Distance

# Infino runs as a separate build+serve process (see
# engine/servers/infino-single-node). The client reaches it over TCP: --host
# gives the address, connection_params (or the env fallback) gives the port, so
# localhost and a remote host are the same code path. The server owns the table
# and column names; the client only sends dim, metric, ids, and vectors.

# Default TCP port; overridden per experiment by connection_params["port"].
INFINO_PORT = int(os.environ.get("INFINO_PORT", "50100"))

# Socket timeouts (seconds): the build phase (create/append/optimize) can be
# slow on a large corpus, so it gets a generous ceiling; search stays tight.
INFINO_BUILD_TIMEOUT_S = float(os.environ.get("INFINO_BUILD_TIMEOUT_S", "3600"))
INFINO_QUERY_TIMEOUT_S = float(os.environ.get("INFINO_QUERY_TIMEOUT_S", "60"))

# Distance -> engine metric key (see infino IndexSpec().vector(col, dim, metric)).
DISTANCE_MAPPING = {
    Distance.COSINE: "cosine",
    Distance.L2: "l2sq",
    Distance.DOT: "negdot",
}
