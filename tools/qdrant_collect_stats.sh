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

VM_RSS_MEMORY_USAGE=$(ssh -t "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "grep VmRSS /proc/\$(pidof qdrant)/status | awk '{print \$2}'")
RSS_ANON_MEMORY_USAGE=$(ssh -t "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "grep RssAnon /proc/\$(pidof qdrant)/status | awk '{print \$2}'")

CURRENT_DATE=$(date +%Y-%m-%d-%H-%M-%S)

echo "$VM_RSS_MEMORY_USAGE" > results/vm-rss-memory-usage-"${CURRENT_DATE}".txt
echo "$RSS_ANON_MEMORY_USAGE" > results/rss-anon-memory-usage-"${CURRENT_DATE}".txt

ROOT_API_RESPONSE=$(ssh -t "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "curl -s http://localhost:6333/")

echo "$ROOT_API_RESPONSE" > results/root-api-"${CURRENT_DATE}".json
