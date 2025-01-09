#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

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

  docker rmi --force qdrant/vector-db-benchmark:latest || true
fi

docker volume create ci-datasets

if [[ "$EXPERIMENT_MODE" == "full" ]] || [[ "$EXPERIMENT_MODE" == "upload" ]]; then
  echo "EXPERIMENT_MODE=$EXPERIMENT_MODE"
  docker run \
    --rm \
    -it \
    --name ci-benchmark-upload \
    -v "$HOME/results:/code/results" \
    -v "ci-datasets:/code/datasets" \
    qdrant/vector-db-benchmark:latest \
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
    qdrant/vector-db-benchmark:latest \
    python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-upload
fi


if [[ "$EXPERIMENT_MODE" == "parallel" ]]; then
  echo "EXPERIMENT_MODE=$EXPERIMENT_MODE"

  docker pull qdrant/vector-db-benchmark:latest

  echo "Starting ci-benchmark-upload container"
  docker run \
    --rm \
    --name ci-benchmark-upload \
    -v "$HOME/results/parallel:/code/results" \
    -v "ci-datasets:/code/datasets" \
    qdrant/vector-db-benchmark:latest \
    python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-search --skip-configure &
  UPLOAD_PID=$!

  echo "Starting ci-benchmark-search container"
  docker run \
    --rm \
    --name ci-benchmark-search \
    -v "$HOME/results/parallel:/code/results" \
    -v "ci-datasets:/code/datasets" \
    qdrant/vector-db-benchmark:latest \
    python run.py --engines "${ENGINE_NAME}" --datasets "${DATASETS}" --host "${PRIVATE_IP_OF_THE_SERVER}" --no-skip-if-exists --skip-upload &
  SEARCH_PID=$!

  echo "Waiting for both containers to finish"
  wait $UPLOAD_PID
  wait $SEARCH_PID

  echo "EXPERIMENT_MODE=$EXPERIMENT_MODE DONE"
fi


if [[ "$EXPERIMENT_MODE" == "snapshot" ]]; then
  echo "EXPERIMENT_MODE=$EXPERIMENT_MODE"

  curl  -X PUT \
    "http://${PRIVATE_IP_OF_THE_SERVER}:6333/collections/benchmark/snapshots/recover" \
    --data-raw "{\"location\": \"${SNAPSHOT_URL}\"}"

  collection_url="http://${PRIVATE_IP_OF_THE_SERVER}:6333/collections/benchmark"
  collection_status=$(curl -s "$collection_url" | jq -r '.result.status')
  counter=0
  while [[ "$collection_status" != "green" && "$counter" -lt 5 ]]; do
    collection_status=$(curl -s "$collection_url" | jq -r '.result.status')
    counter=$(expr $counter + 1)
    sleep 1
  done

  if [[ "$collection_status" == "green" ]]; then
    echo "Experiment stage: Done"
  else
    echo "Experiment interrupted: collection is not ready."
    exit 1
  fi
fi
