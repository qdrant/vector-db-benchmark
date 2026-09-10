# Infino server (single node)

Infino runs as a build+serve process the [Infino client](../../clients/infino)
drives over TCP: the client sends `create`, `append`, `optimize`, and `search`,
so the engine and the benchmark client can run on separate machines.

Infino ships as a Python wheel (not a server image), so there is no container to
pull — you can run the server directly, or use the compose file below to fit the
harness's `docker compose up` convention.

## Run directly (no Docker)

```bash
pip install "infino==0.8.0"                 # first release with build+serve mode
mkdir -p ~/.config/infino
printf 'vector:\n  search_mode: hnsw_ivf\n' > ~/.config/infino/config.yaml
python -m infino._bench_serve --build \
  --data /tmp/infino --table benchmark --col emb --id-col id \
  --addr 0.0.0.0:50100 --cache-bytes 17179869184
```

## Run with Docker (harness convention)

```bash
docker compose -f engine/servers/infino-single-node/docker-compose.yaml up -d --build
```

## Drive it

Point the client at the host with the standard `--host` flag; the port is set in
the experiment's `connection_params` (`50100` by default):

```bash
python run.py --engines infino-hnsw-ivf --datasets glove-100-angular --host <server-host>
```

## Configuration

| variable | default | meaning |
|---|---|---|
| `INFINO_VERSION` | `0.8.0` | published wheel version to install (Docker path) |
| `INFINO_CACHE_BYTES` | `17179869184` (16 GiB) | engine block-cache budget |

> **Version note:** the build+serve mode (`bench_serve_build_tcp`) needs
> `infino>=0.8.0`.
