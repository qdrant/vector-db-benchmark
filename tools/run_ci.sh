#!/bin/bash

set -e

# Script, that runs benchmark within the GitHub Actions CI environment

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

bash -x "${SCRIPT_PATH}/run_remote_benchmark.sh"

# Upload to postgres
# -t sorts by modification time
export SEARCH_RESULTS_FILE=$(ls -t results/*-search-*.json | head -n 1)
export UPLOAD_RESULTS_FILE=$(ls -t results/*-upload-*.json | head -n 1)
export MEMORY_USAGE_FILE=$(ls -t results/memory-usage-*.txt | head -n 1)
export ROOT_API_RESPONSE_FILE=$(ls -t results/root-api-*.json | head -n 1)

bash -x "${SCRIPT_PATH}/upload_results_postgres.sh"
