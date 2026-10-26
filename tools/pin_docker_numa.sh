#!/usr/bin/env bash
# Pin every container in a compose project to the server NUMA SKU.
# Usage: pin_docker_numa.sh /path/to/compose-dir

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=numa_env.sh
source "${SCRIPT_DIR}/numa_env.sh"

COMPOSE_DIR=${1:-.}
if [[ ! -d "$COMPOSE_DIR" ]]; then
    echo "compose dir not found: $COMPOSE_DIR" >&2
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "docker is not installed; cannot pin containers" >&2
    exit 1
fi

mapfile -t CONTAINERS < <(cd "$COMPOSE_DIR" && docker compose ps -q)
if [[ ${#CONTAINERS[@]} -eq 0 ]]; then
    echo "no running containers in $COMPOSE_DIR" >&2
    exit 1
fi

for id in "${CONTAINERS[@]}"; do
    docker update \
        --cpuset-cpus "$SERVER_CPUSET" \
        --cpuset-mems "$SERVER_MEMS" \
        --memory "$SERVER_MEMORY" \
        --memory-swap "$SERVER_MEMORY" \
        "$id"
    echo "pinned ${id:0:12} cpus=${SERVER_CPUSET} mems=${SERVER_MEMS} memory=${SERVER_MEMORY}"
done
