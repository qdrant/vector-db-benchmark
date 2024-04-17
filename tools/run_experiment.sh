#!/bin/bash

set -e

ENGINE_NAME=${ENGINE_NAME:-"qdrant-continuous-benchmark"}

DATASETS=${DATASETS:-""}

PRIVATE_IP_OF_THE_SERVER=${PRIVATE_IP_OF_THE_SERVER:-""}

if [[ -z "$ENGINE_NAME" ]]; then
  echo "ENGINE_NAME is not set"
  exit 1
fi

if [[ -z "$DATASETS" ]]; then
  echo "DATASETS is not set"
  exit 1
fi

if [[ -z "$PRIVATE_IP_OF_THE_SERVER" ]]; then
  echo "PRIVATE_IP_OF_THE_SERVER is not set"
  exit 1
fi

docker rmi --force qdrant/vector-db-benchmark:latest || true

docker run \
  --rm \
  -it \
  -v "$HOME/results:/code/results" \
  qdrant/vector-db-benchmark:latest \
  python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-search

docker run \
  --rm \
  -it \
  -v "$HOME/results:/code/results" \
  qdrant/vector-db-benchmark:latest \
  python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-upload
