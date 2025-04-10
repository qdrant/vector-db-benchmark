#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

function handle_err() {
  echo "qdrant_version=${QDRANT_VERSION}" >> $GITHUB_OUTPUT
  echo "engine_name=${ENGINE_NAME}" >> $GITHUB_OUTPUT
  echo "dataset=${DATASETS}" >> $GITHUB_OUTPUT

  echo "failed=error" >> $GITHUB_OUTPUT
}

function handle_term() {
  echo "qdrant_version=${QDRANT_VERSION}" >> $GITHUB_OUTPUT
  echo "engine_name=${ENGINE_NAME}" >> $GITHUB_OUTPUT
  echo "dataset=${DATASETS}" >> $GITHUB_OUTPUT

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
  export SEARCH_RESULTS_FILE=$(find results/ -type f -name '*-search-*.json' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)
  export UPLOAD_RESULTS_FILE=$(find results/ -type f -name '*-upload-*.json' -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)

  if [[ "$BENCHMARK_STRATEGY" == "parallel" ]]; then
    export PARALLEL_UPLOAD_RESULTS_FILE=$(ls -t results/parallel/*-upload-*.json | head -n 1)
    export PARALLEL_SEARCH_RESULTS_FILE=$(ls -t results/parallel/*-search-*.json | head -n 1)
  fi
fi

export VM_RSS_MEMORY_USAGE_FILE=$(ls -t results/vm-rss-memory-usage-*.txt | head -n 1)
export RSS_ANON_MEMORY_USAGE_FILE=$(ls -t results/rss-anon-memory-usage-*.txt | head -n 1)
export ROOT_API_RESPONSE_FILE=$(ls -t results/root-api-*.json | head -n 1)

export IS_CI_RUN="true"

if [[ "$BENCHMARK_STRATEGY" == "parallel" ]]; then
  bash -x "${SCRIPT_PATH}/upload_parallel_results_postgres.sh"
else
  bash -x "${SCRIPT_PATH}/upload_results_postgres.sh"
fi

