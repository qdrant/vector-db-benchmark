#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

CURRENT_DATE=$(date +%Y-%m-%d-%H-%M-%S)

TELEMETRY_API_RESPONSE=$(ssh -t "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "curl -s http://localhost:6333/telemetry?details_level=10")

echo "$TELEMETRY_API_RESPONSE" > results/telemetry-api-"${CURRENT_DATE}".json
