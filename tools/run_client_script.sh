#!/bin/bash

set -e

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

ssh -tt "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "${RUN_EXPERIMENT}"

LATEST_RESULT=$(ssh "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "ls -t results/ | head -n 1")
# -p preseves modification time, access time, and modes (but not change time)
scp -p "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}:~/results/${LATEST_RESULT}" "${SCRIPT_PATH}/results"
