#!/bin/bash

set -e

# Setup 2 machines in Hetzner Cloud
# One machine will be used as a server, another one as a client

cleanup() {
  echo "cleaning up..."
  bash -x "${SCRIPT_PATH}/tear_down.sh" "$BENCH_SERVER_NAME"
}

trap 'echo signal received!; kill $(jobs -p); wait; cleanup' SIGINT SIGTERM

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")


BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}
BENCH_CLIENT_NAME=${CLIENT_NAME:-"benchmark-client-1"}

trap 'cleanup' EXIT

SERVER_NAME=$BENCH_SERVER_NAME bash -x "${SCRIPT_PATH}/${CLOUD_NAME}/create_and_install.sh" &
SERVER_CREATION_PID=$!
SERVER_NAME=$BENCH_CLIENT_NAME bash -x "${SCRIPT_PATH}/${CLOUD_NAME}/create_and_install.sh"
wait $SERVER_CREATION_PID

SERVER_CONTAINER_NAME=${SERVER_CONTAINER_NAME:-"qdrant-continuous-benchmarks"}

bash -x "${SCRIPT_PATH}/run_server_container.sh" "$SERVER_CONTAINER_NAME"

bash -x "${SCRIPT_PATH}/run_client_script.sh"
