#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

# Setup 2 machines in Hetzner Cloud
# One machine will be used as a server, another one as a client

cleanup() {
  echo "cleaning up file=$BASH_SOURCE"
  #  bash -x "${SCRIPT_PATH}/tear_down.sh"
}

trap 'echo signal received!; kill $(jobs -p); wait; cleanup' SIGINT SIGTERM

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")


BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}
BENCH_CLIENT_NAME=${CLIENT_NAME:-"benchmark-client-1"}

trap 'cleanup' EXIT

# Uncomment this to dynamically create servers

#SERVER_NAME=$BENCH_SERVER_NAME SERVER_TYPE='ccx12' bash -x "${SCRIPT_PATH}/${CLOUD_NAME}/create_and_install.sh" &
#SERVER_CREATION_PID=$!
#SERVER_NAME=$BENCH_CLIENT_NAME SERVER_TYPE='cpx11' bash -x "${SCRIPT_PATH}/${CLOUD_NAME}/create_and_install.sh"
#wait $SERVER_CREATION_PID

SERVER_NAME=$BENCH_SERVER_NAME bash -x "${SCRIPT_PATH}/${CLOUD_NAME}/check_ssh_connection.sh"
SERVER_NAME=$BENCH_CLIENT_NAME bash -x "${SCRIPT_PATH}/${CLOUD_NAME}/check_ssh_connection.sh"


SERVER_CONTAINER_NAME=${SERVER_CONTAINER_NAME:-"qdrant-continuous-benchmarks"}

bash -x "${SCRIPT_PATH}/run_server_container.sh" "$SERVER_CONTAINER_NAME"

bash -x "${SCRIPT_PATH}/run_client_script.sh"

bash -x "${SCRIPT_PATH}/qdrant_collect_stats.sh" "$SERVER_CONTAINER_NAME"
