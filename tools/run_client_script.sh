#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO '
set -euo pipefail

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}
BENCH_CLIENT_NAME=${CLIENT_NAME:-"benchmark-client-1"}

IP_OF_THE_CLIENT=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_CLIENT_NAME")

scp "${SCRIPT_PATH}/run_experiment.sh" "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}:~/run_experiment.sh"

ENGINE_NAME=${ENGINE_NAME:-"qdrant-continuous-benchmark"}

DATASETS=${DATASETS:-"laion-small-clip"}

PRIVATE_IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_private_ip.sh" "$BENCH_SERVER_NAME")

RUN_EXPERIMENT="ENGINE_NAME=${ENGINE_NAME} DATASETS=${DATASETS} PRIVATE_IP_OF_THE_SERVER=${PRIVATE_IP_OF_THE_SERVER} bash ~/run_experiment.sh"

ssh -tt -o ServerAliveInterval=60 -o ServerAliveCountMax=3 "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "${RUN_EXPERIMENT}"

SEARCH_RESULT_FILE=$(ssh "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "ls -t results/*-search-*.json | head -n 1")
UPLOAD_RESULT_FILE=$(ssh "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "ls -t results/*-upload-*.json | head -n 1")
VM_RSS_MEMORY_USAGE_FILE=$(ssh "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "ls -t results/vm-rss-memory-usage-*.txt | head -n 1")
RSS_ANON_MEMORY_USAGE_FILE=$(ssh "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "ls -t results/rss-anon-memory-usage-*.txt | head -n 1")

mkdir -p results

for RESULT_FILE in $SEARCH_RESULT_FILE $UPLOAD_RESULT_FILE $MEMORY_USAGE_FILE; do
    # -p preseves modification time, access time, and modes (but not change time)
    scp -p "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}:~/${RESULT_FILE}" "./results"
done
