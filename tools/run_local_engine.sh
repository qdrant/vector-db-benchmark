#!/usr/bin/env bash
# Start one engine on this host, pin it to NUMA node 0, run the client on node 1.
# Usage: run_local_engine.sh <compose-dir-name> <engine-glob> [dataset,dataset,...]

set -euo pipefail

SERVER_PATH=$1
ENGINE_NAME=$2
DATASETS=${3:-${DATASETS:-"glove-100-angular"}}

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=python_env.sh
source "${ROOT_DIR}/tools/python_env.sh"
# shellcheck source=numa_env.sh
source "${ROOT_DIR}/tools/numa_env.sh" --print

COMPOSE_DIR="${ROOT_DIR}/engine/servers/${SERVER_PATH}"
# ENGINE_NAME is a comma-separated HNSW grid; that string exceeds NAME_MAX.
# Use the compose directory (one engine per call) so the mv cannot abort the run.
MONITOR_PATH=$(echo "$SERVER_PATH" | sed -e 's/[^A-Za-z0-9._-]/_/g')

dataset_args=()
IFS=',' read -ra ds <<< "$DATASETS"
for dataset in "${ds[@]}"; do
    dataset_args+=(--datasets "$dataset")
done

engine_args=()
IFS=',' read -ra engs <<< "$ENGINE_NAME"
for engine in "${engs[@]}"; do
    engine_args+=(--engines "$engine")
done

MONITOR_DIR="${BENCHMARK_MONITORING_DIR:-${ROOT_DIR}/monitoring}"
mkdir -p "${MONITOR_DIR}/results"
(
    cd "${MONITOR_DIR}"
    rm -f docker.stats.jsonl
    if command -v docker >/dev/null 2>&1; then
        nohup bash "${ROOT_DIR}/monitoring/monitor_docker.sh" >/dev/null 2>&1 &
    fi
)

wait_for_port() {
    local port=$1
    local timeout=${2:-180}
    local i
    for ((i = 1; i <= timeout; i++)); do
        if (echo >/dev/tcp/127.0.0.1/"$port") 2>/dev/null; then
            echo "engine port ${port} is up after ${i}s"
            return 0
        fi
        sleep 1
    done
    echo "timed out waiting for 127.0.0.1:${port}" >&2
    return 1
}

engine_port() {
    case "$SERVER_PATH" in
        qdrant-*) echo 6333 ;;
        weaviate-*) echo 8090 ;;
        milvus-*) echo 19530 ;;
        elasticsearch-*) echo 9200 ;;
        opensearch-*) echo 9200 ;;
        redis-*) echo 6379 ;;
        pgvector-*) echo 5432 ;;
        *) echo "" ;;
    esac
}

cleanup_engine() {
    (cd "$COMPOSE_DIR" && docker compose down) || true
}
trap cleanup_engine EXIT

cd "$COMPOSE_DIR"
docker compose down || true
export QDRANT_OPTIMIZER_CPU_BUDGET QDRANT_MAX_SEARCH_THREADS
docker compose up -d
port=$(engine_port)
if [[ -n "$port" ]]; then
    wait_for_port "$port" 180
else
    sleep 30
fi
if [[ "$SERVER_PATH" == elasticsearch-* || "$SERVER_PATH" == opensearch-* ]]; then
    "${ROOT_DIR}/tools/wait_for_green_status.sh" "localhost:${port}"
fi
"${ROOT_DIR}/tools/pin_docker_numa.sh" "$COMPOSE_DIR"
sleep 5

extra_args=()
if [[ -n "${RUN_PY_ARGS:-}" ]]; then
    # shellcheck disable=SC2206
    extra_args=($RUN_PY_ARGS)
fi

cd "$ROOT_DIR"
if [[ -x /usr/bin/numactl ]]; then
    numactl --physcpubind="$CLIENT_CPUSET" --membind="$CLIENT_MEMS" \
        "${BENCHMARK_PYTHON}" run.py "${engine_args[@]}" "${dataset_args[@]}" \
        --host localhost "${extra_args[@]}"
else
    echo "numactl missing; running the client unpinned" >&2
    "${BENCHMARK_PYTHON}" run.py "${engine_args[@]}" "${dataset_args[@]}" \
        --host localhost "${extra_args[@]}"
fi

if [[ -f "${MONITOR_DIR}/docker.stats.jsonl" ]]; then
    mv "${MONITOR_DIR}/docker.stats.jsonl" \
        "${MONITOR_DIR}/results/${MONITOR_PATH}-docker.stats.jsonl" || true
fi
