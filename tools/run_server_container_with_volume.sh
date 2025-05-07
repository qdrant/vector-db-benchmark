#!/bin/bash

set -e

# Examples: qdrant-continuous-benchmarks-with-volume
CONTAINER_NAME=$1
CONTAINER_MEM_LIMIT=${2:-"25Gb"}
EXECUTION_MODE=${3:-"init"}

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}


SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

QDRANT_VERSION=${QDRANT_VERSION:-"dev"}
QDRANT__FEATURE_FLAGS__ALL=${QDRANT__FEATURE_FLAGS__ALL:-"false"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

bash -x "${SCRIPT_PATH}/sync_servers.sh" "root@$IP_OF_THE_SERVER"

# if version is starts with "docker" or "ghcr", use container
if [[ ${QDRANT_VERSION} == docker/* ]] || [[ ${QDRANT_VERSION} == ghcr/* ]]; then

    if [[ ${QDRANT_VERSION} == docker/* ]]; then
        # pull from docker hub
        QDRANT_VERSION=${QDRANT_VERSION#docker/}
        CONTAINER_REGISTRY='docker.io'
    elif [[ ${QDRANT_VERSION} == ghcr/* ]]; then
        # pull from github container registry
        QDRANT_VERSION=${QDRANT_VERSION#ghcr/}
        CONTAINER_REGISTRY='ghcr.io'
    fi

    if [[ "$EXECUTION_MODE" == "init" ]]; then
      echo "Initialize qdrant from scratch, with qdrant_storage volume"
      DOCKER_COMPOSE="export QDRANT_VERSION=${QDRANT_VERSION}; export CONTAINER_REGISTRY=${CONTAINER_REGISTRY}; export CONTAINER_MEM_LIMIT=${CONTAINER_MEM_LIMIT}; export QDRANT__FEATURE_FLAGS__ALL=${QDRANT__FEATURE_FLAGS__ALL}; docker compose down; pkill qdrant; docker rm -f qdrant-continuous || true; docker rmi -f ${CONTAINER_REGISTRY}/qdrant/qdrant:${QDRANT_VERSION} || true; docker volume rm -f qdrant_storage || true; docker compose up -d; docker container ls -a"
    elif [[ "$EXECUTION_MODE" == "continue" ]]; then
      # suggest that volume qdrant_storage exist and start qdrant
      echo "Reload qdrant with existing data"
      DOCKER_COMPOSE="export QDRANT_VERSION=${QDRANT_VERSION}; export CONTAINER_REGISTRY=${CONTAINER_REGISTRY}; export CONTAINER_MEM_LIMIT=${CONTAINER_MEM_LIMIT}; export QDRANT__FEATURE_FLAGS__ALL=${QDRANT__FEATURE_FLAGS__ALL}; docker compose down; pkill qdrant; docker rm -f qdrant-continuous || true; docker rmi -f ${CONTAINER_REGISTRY}/qdrant/qdrant:${QDRANT_VERSION} || true ; sudo bash -c 'sync; echo 1 > /proc/sys/vm/drop_caches'; docker compose up -d; docker container ls -a"
    else
      echo "Error: unknown execution mode ${EXECUTION_MODE}. Execution mode should be 'init' or 'continue'"
      exit 1
    fi

    ssh -t  -o ServerAliveInterval=60 -o ServerAliveCountMax=3 "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "cd ./projects/vector-db-benchmark/engine/servers/${CONTAINER_NAME} ; $DOCKER_COMPOSE"
else
    echo "Error: unknown version ${QDRANT_VERSION}. Version name should start with 'docker/' or 'ghcr/'"
    exit 1
fi
