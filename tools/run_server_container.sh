#!/bin/bash

set -e

# Examples: qdrant-single-node, qdrant-single-node-rps
CONTAINER_NAME=$1

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}


SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}
BENCH_CLIENT_NAME=${CLIENT_NAME:-"benchmark-client-1"}

IP_OF_THE_CLIENT=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_CLIENT_NAME")

PRIVATE_IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_private_ip.sh" "$BENCH_SERVER_NAME")


COMMAND="python3 run.py --engines \"${ENGINE_NAME}\" --datasets \"${DATASETS}\" --host \"${PRIVATE_IP_OF_THE_SERVER}\""


ssh -t "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "cd ./projects/vector-db-benchmark/engine/servers/${CONTAINER_NAME} ; $COMMAND"

