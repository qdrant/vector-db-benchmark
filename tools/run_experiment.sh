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
  for i in 1 2 3; do
    echo "${GHCR_PASSWORD}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin && break
    echo "docker login attempt ${i} failed, retrying in $((i * 10))s..."
    sleep $((i * 10))
  done
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

# Mount custom configurations if available
CONFIGURATIONS_MOUNT=""
if [[ -d "$HOME/configurations" ]]; then
  echo "Found custom configurations directory, will mount into container"
  CONFIGURATIONS_MOUNT="$HOME/configurations:/code/experiments/configurations"
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
    ${CONFIGURATIONS_MOUNT:+"-v" "$CONFIGURATIONS_MOUNT"} \
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
    ${CONFIGURATIONS_MOUNT:+"-v" "$CONFIGURATIONS_MOUNT"} \
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
    ${CONFIGURATIONS_MOUNT:+"-v" "$CONFIGURATIONS_MOUNT"} \
    "${VECTOR_DB_BENCHMARK_IMAGE}" \
    python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-search --skip-configure &
  UPLOAD_PID=$!

  echo "Starting ci-benchmark-search container"
  docker run \
    --rm \
    --name ci-benchmark-search \
    -v "$HOME/results/parallel:/code/results" \
    -v "ci-datasets:/code/datasets" \
    ${CONFIGURATIONS_MOUNT:+"-v" "$CONFIGURATIONS_MOUNT"} \
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
  # wait=false: outer wall-clock kills fire before huge snapshots finish syncing.
  echo "Kicking off async snapshot recovery (wait=false)"
  curl -X PUT \
    "http://${PRIVATE_IP_OF_THE_SERVER}:6333/collections/benchmark/snapshots/recover?wait=false" \
    --data-raw "{\"location\": \"${SNAPSHOT_URL}\"}"
  echo ""
  echo "Recovery dispatched; polling for green status"

  collection_url="http://${PRIVATE_IP_OF_THE_SERVER}:6333/collections/benchmark"
  collection_status=$(curl -s "$collection_url" | jq -r '.result.status')
  echo "Experiment stage: collection status is ${collection_status} after recovery"

  WAIT_TIMEOUT_S=5400
  WAIT_INTERVAL_S=5
  HEARTBEAT_S=60
  elapsed=0
  last_logged_status=""
  last_log_at=0
  while [[ "$collection_status" != "green" ]]; do
    if (( elapsed >= WAIT_TIMEOUT_S )); then
      echo "Timeout: collection still '${collection_status}' after ${WAIT_TIMEOUT_S}s"
      exit 1
    fi
    sleep "$WAIT_INTERVAL_S"
    elapsed=$((elapsed + WAIT_INTERVAL_S))
    collection_status=$(curl -s "$collection_url" | jq -r '.result.status')
    if [[ "$collection_status" != "$last_logged_status" ]] || (( elapsed - last_log_at >= HEARTBEAT_S )); then
      echo "  ... status=${collection_status} (waited ${elapsed}s)"
      last_logged_status=$collection_status
      last_log_at=$elapsed
    fi
  done
  echo "Collection is green after ${elapsed}s"

fi
