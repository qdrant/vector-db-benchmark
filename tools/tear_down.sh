#!/bin/bash

set -e

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}
BENCH_CLIENT_NAME=${CLIENT_NAME:-"benchmark-client-1"}

bash -x "${SCRIPT_PATH}/${CLOUD_NAME}/remove_server.sh" "$BENCH_SERVER_NAME"
bash -x "${SCRIPT_PATH}/${CLOUD_NAME}/remove_server.sh" "$BENCH_CLIENT_NAME"