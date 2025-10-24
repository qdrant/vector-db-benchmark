#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

VECTOR_DB_BENCHMARK_IMAGE=${VECTOR_DB_BENCHMARK_IMAGE:-"qdrant/vector-db-benchmark:latest"}
GHCR_PASSWORD=${GHCR_PASSWORD:-""}
GHCR_USERNAME=${GHCR_USERNAME:-""}

if [[ -n "${GHCR_PASSWORD}" ]] || [[ "${VECTOR_DB_BENCHMARK_IMAGE}" == ghcr.io/* ]]; then
  if [[ -z "${GHCR_PASSWORD}" ]] || [[ -z "${GHCR_USERNAME}" ]]; then
    echo "GHCR_PASSWORD and GHCR_USERNAME is required to pull images from ghcr.io"
    exit 1
  fi
  echo "${GHCR_PASSWORD}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin
fi

ENGINE_NAME=${ENGINE_NAME:-"qdrant-continuous-benchmark"}

DATASETS=${DATASETS:-""}

PRIVATE_IP_OF_THE_SERVER=${PRIVATE_IP_OF_THE_SERVER:-""}

EXPERIMENT_MODE=${EXPERIMENT_MODE:-"full"}

SNAPSHOT_URL=${SNAPSHOT_URL:-""}

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
  echo "EXPERIMENT_MODE is not set, possible values are: full | upload | search | snapshot | parallel"
  exit 1
fi

if [[ "$EXPERIMENT_MODE" == "snapshot" ]] && [[ -z "$SNAPSHOT_URL" ]]; then
  echo "EXPERIMENT_MODE is 'snapshot' but SNAPSHOT_URL is not set"
  exit 1
fi

if [[ "$EXPERIMENT_MODE" != "snapshot" ]]; then
  docker container rm -f ci-benchmark-upload || true
  docker container rm -f ci-benchmark-search || true

  docker rmi --force "${VECTOR_DB_BENCHMARK_IMAGE}" || true
fi

echo "Ensure datasets volume exists and contains latest datasets.json"
docker volume create ci-datasets
if [[ -f "$HOME/datasets.json" ]]; then
  echo "Found datasets.json, move it into the volume"
  mv ~/datasets.json "$(docker volume inspect ci-datasets -f '{{ .Mountpoint }}')"
else
  echo "datasets.json is missing, skip moving it into the volume"
fi

if [[ "$EXPERIMENT_MODE" == "full" ]] || [[ "$EXPERIMENT_MODE" == "upload" ]]; then
  echo "EXPERIMENT_MODE=$EXPERIMENT_MODE"
  docker run \
    --rm \
    -it \
    --name ci-benchmark-upload \
    -v "$HOME/results:/code/results" \
    -v "ci-datasets:/code/datasets" \
    "${VECTOR_DB_BENCHMARK_IMAGE}" \
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
    -v "ci-datasets:/code/datasets" \
    "${VECTOR_DB_BENCHMARK_IMAGE}" \
    python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-upload
fi


if [[ "$EXPERIMENT_MODE" == "parallel" ]]; then
  echo "EXPERIMENT_MODE=$EXPERIMENT_MODE"

  docker pull "${VECTOR_DB_BENCHMARK_IMAGE}"

  echo "Starting ci-benchmark-upload container"
  docker run \
    --rm \
    --name ci-benchmark-upload \
    -v "$HOME/results/parallel:/code/results" \
    -v "ci-datasets:/code/datasets" \
    "${VECTOR_DB_BENCHMARK_IMAGE}" \
    python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-search --skip-configure &
  UPLOAD_PID=$!

  echo "Starting ci-benchmark-search container"
  docker run \
    --rm \
    --name ci-benchmark-search \
    -v "$HOME/results/parallel:/code/results" \
    -v "ci-datasets:/code/datasets" \
    "${VECTOR_DB_BENCHMARK_IMAGE}" \
    python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-upload &
  SEARCH_PID=$!

  echo "Waiting for both containers to finish"
  wait $UPLOAD_PID
  wait $SEARCH_PID

  echo "EXPERIMENT_MODE=$EXPERIMENT_MODE DONE"
fi


if [[ "$EXPERIMENT_MODE" == "snapshot" ]]; then
  echo "EXPERIMENT_MODE=$EXPERIMENT_MODE"
  echo "Recovering collection from snapshot"
  curl  -X PUT \
    "http://${PRIVATE_IP_OF_THE_SERVER}:6333/collections/benchmark/snapshots/recover" \
    --data-raw "{\"location\": \"${SNAPSHOT_URL}\"}"
  echo ""
  echo "Done recovering collection from snapshot"

  collection_url="http://${PRIVATE_IP_OF_THE_SERVER}:6333/collections/benchmark"
  collection_status=$(curl -s "$collection_url" | jq -r '.result.status')
  echo "Experiment stage: collection status is ${collection_status} after recovery"

fi
