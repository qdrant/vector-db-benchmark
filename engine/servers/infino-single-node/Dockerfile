# Infino build+serve container for the benchmark's client-server topology.
#
# Infino ships as a Python wheel (no standalone server image), so this installs
# the published wheel and runs its benchmark build+serve process, which the
# Infino client drives over TCP (create / append / optimize / search).
FROM python:3.12-slim

# Pin the published wheel. 0.8.0 is the first release with the build+serve mode
# (bench_serve_build_tcp); override INFINO_VERSION to pin a newer one.
ARG INFINO_VERSION=0.8.0
RUN pip install --no-cache-dir "infino==${INFINO_VERSION}"

# Serving path: hnsw_ivf builds + serves a resident HNSW graph over the
# quantized vectors. The engine reads this from XDG_CONFIG_HOME/infino/config.yaml.
ENV XDG_CONFIG_HOME=/etc/xdg
RUN mkdir -p /etc/xdg/infino \
    && printf 'vector:\n  search_mode: hnsw_ivf\n' > /etc/xdg/infino/config.yaml

# Block-cache budget (bytes) for the engine; override at runtime.
ENV INFINO_CACHE_BYTES=17179869184

WORKDIR /data
EXPOSE 50100

# One table ("benchmark") with an int64 "id" and a float32 "emb" vector column,
# matching the client (engine/clients/infino/config.py). --build accepts writes
# and optimize over the wire; bind on all interfaces for a remote client.
CMD ["sh", "-c", "python -m infino._bench_serve --build \
  --data /data/infino --table benchmark --col emb --id-col id \
  --addr 0.0.0.0:50100 --cache-bytes ${INFINO_CACHE_BYTES}"]
