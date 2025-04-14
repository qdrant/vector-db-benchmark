#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

# Possible values are: full|upload|search|parallel|snapshot
EXPERIMENT_MODE=${1:-"full"}

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}
BENCH_CLIENT_NAME=${CLIENT_NAME:-"benchmark-client-1"}

IP_OF_THE_CLIENT=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_CLIENT_NAME")

ENGINE_NAME=${ENGINE_NAME:-"qdrant-continuous-benchmark"}

DATASETS=${DATASETS:-"laion-small-clip"}

SNAPSHOT_URL=${SNAPSHOT_URL:-""}

PRIVATE_IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_private_ip.sh" "$BENCH_SERVER_NAME")

if [[ "$EXPERIMENT_MODE" == "snapshot" ]]; then
  scp "${SCRIPT_PATH}/run_experiment.sh" "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}:~/run_experiment_snapshot.sh"

  RUN_EXPERIMENT="ENGINE_NAME=${ENGINE_NAME} \
  DATASETS=${DATASETS} \
  PRIVATE_IP_OF_THE_SERVER=${PRIVATE_IP_OF_THE_SERVER} \
  EXPERIMENT_MODE=${EXPERIMENT_MODE} \
  SNAPSHOT_URL=${SNAPSHOT_URL} \
  bash ~/run_experiment_snapshot.sh"

  ssh -tt -o ServerAliveInterval=120 -o ServerAliveCountMax=10 "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "${RUN_EXPERIMENT}"

else
  scp "${SCRIPT_PATH}/run_experiment.sh" "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}:~/run_experiment.sh"
  scp "${SCRIPT_PATH}/../datasets/datasets.json" "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}:~/datasets.json"

  RUN_EXPERIMENT="ENGINE_NAME=${ENGINE_NAME} \
  DATASETS=${DATASETS} \
  PRIVATE_IP_OF_THE_SERVER=${PRIVATE_IP_OF_THE_SERVER} \
  EXPERIMENT_MODE=${EXPERIMENT_MODE} \
  bash ~/run_experiment.sh"

  ssh -tt -o ServerAliveInterval=60 -o ServerAliveCountMax=3 "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "${RUN_EXPERIMENT}"

fi

echo "Gather experiment results..."
result_files_arr=()
result_parallel_files_arr=()

if [[ "$EXPERIMENT_MODE" == "full" ]] || [[ "$EXPERIMENT_MODE" == "upload" ]]; then
  UPLOAD_RESULT_FILE=$(ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=10 "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "find results/ -maxdepth 1 -type f -name '*-upload-*.json' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-")
  result_files_arr+=("$UPLOAD_RESULT_FILE")
fi

if [[ "$EXPERIMENT_MODE" == "full" ]] || [[ "$EXPERIMENT_MODE" == "search" ]]; then
  SEARCH_RESULT_FILE=$(ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=10 "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "find results/ -maxdepth 1 -type f -name '*-search-*.json' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-")
  result_files_arr+=("$SEARCH_RESULT_FILE")
fi

if [[ "$EXPERIMENT_MODE" == "parallel" ]]; then
  UPLOAD_RESULT_FILE=$(ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=10 "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "ls -t results/parallel/*-upload-*.json | head -n 1")
  result_parallel_files_arr+=("$UPLOAD_RESULT_FILE")

  SEARCH_RESULT_FILE=$(ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=10 "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}" "ls -t results/parallel/*-search-*.json | head -n 1")
  result_parallel_files_arr+=("$SEARCH_RESULT_FILE")
fi

mkdir -p results
mkdir -p results/parallel

for RESULT_FILE in "${result_files_arr[@]}"; do
    # -p preseves modification time, access time, and modes (but not change time)
    scp -o ServerAliveInterval=10 -o ServerAliveCountMax=10 -p "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}:~/${RESULT_FILE}" "./results"
done

for RESULT_FILE in "${result_parallel_files_arr[@]}"; do
    scp -o ServerAliveInterval=10 -o ServerAliveCountMax=10 -p "${SERVER_USERNAME}@${IP_OF_THE_CLIENT}:~/${RESULT_FILE}" "./results/parallel"
done
