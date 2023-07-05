#!/bin/bash

set -e

# Script, that runs benchmark within the GitHub Actions CI environment

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

# Set up dependencies

apt update
apt install -y jq

# Download and install hcloud

HCVERSION=v1.36.0

wget https://github.com/hetznercloud/cli/releases/download/${HCVERSION}/hcloud-linux-amd64.tar.gz

tar xzf hcloud-linux-amd64.tar.gz

mv hcloud /usr/local/bin

# Install mc

wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
./mc alias set qdrant https://storage.googleapis.com "${GCS_KEY}" "${GCS_SECRET}"

bash -x "${SCRIPT_PATH}/run_remote_benchmark.sh"

./mc cp results/* qdrant/vector-search-engines-benchmark/results/ci/qdrant/
