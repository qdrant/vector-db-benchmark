#!/bin/bash

set -e

# Script, that runs benchmark within the GitHub Actions CI environment

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

# Set up dependencies

sudo apt update
sudo apt install -y jq

# Download and install hcloud

HCVERSION=v1.36.0

wget https://github.com/hetznercloud/cli/releases/download/${HCVERSION}/hcloud-linux-amd64.tar.gz

tar xzf hcloud-linux-amd64.tar.gz

sudo mv hcloud /usr/local/bin

# Install mc

wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
./mc alias set qdrant https://storage.googleapis.com "${GCS_KEY}" "${GCS_SECRET}"

bash -x "${SCRIPT_PATH}/run_remote_benchmark.sh"

./mc cp results/* qdrant/vector-search-engines-benchmark/results/ci/qdrant/

# Upload to postgres

export SEARCH_RESULTS_FILE=$(ls results/*-search-*.json | head -n 1)
export UPLOAD_RESULTS_FILE=$(ls results/*-upload-*.json | head -n 1)
export MEMEORY_USAGE_FILE=$(ls results/memory-usage-*.txt | head -n 1)

bash -x "${SCRIPT_PATH}/upload_results_postgres.sh"
