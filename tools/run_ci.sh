#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE func=${FUNCNAME[0]} '
set -euo pipefail

function handle_err() {
  echo "Error occured qdrant_version=${QDRANT_VERSION} engine_name=${ENGINE_NAME} dataset=${DATASETS}"
  echo "{failed}={error}" >> $GITHUB_OUTPUT
}

function handle_term() {
  echo "Timeout occured qdrant_version=${QDRANT_VERSION} engine_name=${ENGINE_NAME} dataset=${DATASETS}"
  echo "{failed}={timeout}" >> $GITHUB_OUTPUT
}

trap 'handle_err' ERR
trap 'handle_term' TERM

# Script, that runs benchmark within the GitHub Actions CI environment

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

bash -x "${SCRIPT_PATH}/run_remote_benchmark.sh"

# Upload to postgres
# -t sorts by modification time
export SEARCH_RESULTS_FILE=$(ls -t results/*-search-*.json | head -n 1)
export UPLOAD_RESULTS_FILE=$(ls -t results/*-upload-*.json | head -n 1)
export VM_RSS_MEMORY_USAGE_FILE=$(ls -t results/vm-rss-memory-usage-*.txt | head -n 1)
export RSS_ANON_MEMORY_USAGE_FILE=$(ls -t results/rss-anon-memory-usage-*.txt | head -n 1)
export ROOT_API_RESPONSE_FILE=$(ls -t results/root-api-*.json | head -n 1)

bash -x "${SCRIPT_PATH}/upload_results_postgres.sh"
