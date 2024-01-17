#!/bin/bash

set -e

# Examples: qdrant-single-node
CONTAINER_NAME=$1

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}


SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

QDRANT_VERSION=${QDRANT_VERSION:-"dev"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

bash -x "${SCRIPT_PATH}/sync_servers.sh" "root@$IP_OF_THE_SERVER"

# if version is dev or if starts with "docker" or "ghcr", use container
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

    DOCKER_COMPOSE="export QDRANT_VERSION=${QDRANT_VERSION}; export CONTAINER_REGISTRY=${CONTAINER_REGISTRY}; docker compose down ; pkill qdrant ; docker rmi ${CONTAINER_REGISTRY}/qdrant/qdrant:${QDRANT_VERSION} || true ; docker compose up -d"
    ssh -t "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "cd ./projects/vector-db-benchmark/engine/servers/${CONTAINER_NAME} ; $DOCKER_COMPOSE"
else
    # else run natively in the server
    DOCKER_QDRANT_STOP="docker stop qdrant-continuous || true"
    QDRANT_BUILD="source ~/.cargo/env; git fetch --tags; git checkout ${QDRANT_VERSION}; git pull; mold -run cargo run --bin qdrant --release"
    ssh -t "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "cd ./projects/qdrant; ${DOCKER_QDRANT_STOP}; $QDRANT_BUILD"
fi
