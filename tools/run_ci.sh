#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

function handle_err() {
  echo "reason=\"Error occurred qdrant_version=${QDRANT_VERSION} engine_name=${ENGINE_NAME} dataset=${DATASETS}\"" >> $GITHUB_OUTPUT
  echo "failed=error" >> $GITHUB_OUTPUT
}

function handle_term() {
  echo "reason=\"Timeout occurred qdrant_version=${QDRANT_VERSION} engine_name=${ENGINE_NAME} dataset=${DATASETS}\"" >> $GITHUB_OUTPUT
  echo "failed=timeout" >> $GITHUB_OUTPUT
}

trap 'handle_err' ERR
trap 'handle_term' TERM

# Script, that runs benchmark within the GitHub Actions CI environment

BENCHMARK_STRATEGY=${BENCHMARK_STRATEGY:-"default"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

bash -x "${SCRIPT_PATH}/run_remote_benchmark.sh"

# Upload to postgres
# -t sorts by modification time
if [[ "$BENCHMARK_STRATEGY" == "collection-reload" ]]; then
  export TELEMETRY_API_RESPONSE_FILE=$(ls -t results/telemetry-api-*.json | head -n 1)
else
  # any other strategies are considered to have search & upload results
  export SEARCH_RESULTS_FILE=$(ls -t results/*-search-*.json | head -n 1)
  export UPLOAD_RESULTS_FILE=$(ls -t results/*-upload-*.json | head -n 1)
fi

export VM_RSS_MEMORY_USAGE_FILE=$(ls -t results/vm-rss-memory-usage-*.txt | head -n 1)
export RSS_ANON_MEMORY_USAGE_FILE=$(ls -t results/rss-anon-memory-usage-*.txt | head -n 1)
export ROOT_API_RESPONSE_FILE=$(ls -t results/root-api-*.json | head -n 1)

bash -x "${SCRIPT_PATH}/upload_results_postgres.sh"
