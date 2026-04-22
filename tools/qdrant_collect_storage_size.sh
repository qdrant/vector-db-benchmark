#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

# Examples: qdrant-continuous-benchmarks, qdrant-continuous-benchmarks-with-volume
CONTAINER_NAME=${1:-"qdrant-continuous-benchmarks"}

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}

# The docker container_name is the same across all qdrant-continuous-* compose files.
QDRANT_DOCKER_CONTAINER=${QDRANT_DOCKER_CONTAINER:-"qdrant-continuous"}
QDRANT_STORAGE_PATH=${QDRANT_STORAGE_PATH:-"/qdrant/storage"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

source "$SCRIPT_PATH/ssh.sh"

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

STORAGE_SIZE_ALLOCATED=$(ssh_with_retry -tt -o ServerAliveInterval=10 -o ServerAliveCountMax=10 "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "docker exec ${QDRANT_DOCKER_CONTAINER} du -s --block-size=1 ${QDRANT_STORAGE_PATH} | awk '{print \$1}'")
STORAGE_SIZE_APPARENT=$(ssh_with_retry -tt -o ServerAliveInterval=10 -o ServerAliveCountMax=10 "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "docker exec ${QDRANT_DOCKER_CONTAINER} du -sb ${QDRANT_STORAGE_PATH} | awk '{print \$1}'")

STORAGE_SIZE_ALLOCATED=$(echo "$STORAGE_SIZE_ALLOCATED" | tr -d '[:space:]')
STORAGE_SIZE_APPARENT=$(echo "$STORAGE_SIZE_APPARENT" | tr -d '[:space:]')

CURRENT_DATE=$(date +%Y-%m-%d-%H-%M-%S)

echo "$STORAGE_SIZE_ALLOCATED" > results/storage-size-allocated-"${CURRENT_DATE}".txt
echo "$STORAGE_SIZE_APPARENT" > results/storage-size-apparent-"${CURRENT_DATE}".txt