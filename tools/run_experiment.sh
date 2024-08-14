#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

ENGINE_NAME=${ENGINE_NAME:-"qdrant-continuous-benchmark"}

DATASETS=${DATASETS:-""}

PRIVATE_IP_OF_THE_SERVER=${PRIVATE_IP_OF_THE_SERVER:-""}

EXPERIMENT_MODE=${EXPERIMENT_MODE:-"full"}

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

if [[ -z "$EXPERIMENT_MODE" ]]; then
  echo "EXPERIMENT_MODE is not set"
  exit 1
fi
docker container rm -f ci-benchmark-upload || true
docker container rm -f ci-benchmark-search || true

docker rmi --force qdrant/vector-db-benchmark:latest || true

if [[ "$EXPERIMENT_MODE" == "full" ]] || [[ "$EXPERIMENT_MODE" == "upload" ]]; then
  echo "EXPERIMENT_MODE=$EXPERIMENT_MODE"
  docker run \
    --rm \
    -it \
    --name ci-benchmark-upload \
    -v "$HOME/results:/code/results" \
    ghcr.io/qdrant/vector-db-benchmark:el_latest \
    python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-search
fi


if [[ "$EXPERIMENT_MODE" == "full" ]] || [[ "$EXPERIMENT_MODE" == "search" ]]; then
  echo "EXPERIMENT_MODE=$EXPERIMENT_MODE"

  if [[ "$EXPERIMENT_MODE" == "search" ]]; then
    echo "Drop caches before running the experiment"
    sudo bash -c 'sync; echo 1 > /proc/sys/vm/drop_caches'
  fi

  docker run \
    --rm \
    -it \
    --name ci-benchmark-search \
    -v "$HOME/results:/code/results" \
    ghcr.io/qdrant/vector-db-benchmark:el_latest \
    python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-upload
fi
