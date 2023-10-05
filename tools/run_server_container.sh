#!/bin/bash

set -e

# Examples: qdrant-single-node, qdrant-single-node-rps
CONTAINER_NAME=$1

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}


SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

QDRANT_VERSION=${QDRANT_VERSION:-"dev"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

bash -x "${SCRIPT_PATH}/sync_servers.sh" "root@$IP_OF_THE_SERVER"

if [ "${QDRANT_VERSION}" == "dev" ]; then
    # if version is dev, run in docker
    DOCKER_COMPOSE="export QDRANT_VERSION=${QDRANT_VERSION}; docker compose down ; docker rmi qdrant/qdrant:${QDRANT_VERSION} || true ; docker compose up -d"
    ssh -t "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "cd ./projects/vector-db-benchmark/engine/servers/${CONTAINER_NAME} ; $DOCKER_COMPOSE"
else
    # else run natively in the server
    DOCKER_QDRANT_STOP="docker stop qdrant-continuous || true"
    QDRANT_BUILD="git checkout ${QDRANT_VERSION}; nohup mold -run cargo run --bin qdrant --release &"
    ssh -T "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "cd ./projects/qdrant; ${DOCKER_QDRANT_STOP}; $QDRANT_BUILD"
fi
