#!/bin/bash

set -e

# Examples: qdrant-single-node, qdrant-single-node-rps
CONTAINER_NAME=$1

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}


SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

MEMORY_USAGE=$(ssh -t "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "grep VmRSS /proc/\$(pidof qdrant)/status | awk '{print \$2}'")

CURRENT_DATE=$(date +%Y-%m-%d-%H-%M-%S)

echo $MEMORY_USAGE > ${SCRIPT_PATH}/results/memory-usage-latest.txt

# echo $MEMORY_USAGE > ${SCRIPT_PATH}/results/memory-usage-${CURRENT_DATE}.txt
