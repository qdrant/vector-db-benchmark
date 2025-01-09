#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_CLIENT_NAME=${CLIENT_NAME:-"benchmark-client-1"}

IP_OF_THE_CLIENT=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_CLIENT_NAME")

echo "Remove ci-datasets volume from client"
RUN_CMD="docker volume rm -f ci-datasets || true"

ssh -tt -o ServerAliveInterval=120 -o ServerAliveCountMax=10 "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "${RUN_CMD}"
