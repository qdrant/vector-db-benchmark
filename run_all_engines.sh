#!/usr/bin/env bash

set -e

DATASETS=${DATASETS:-"*"}

SERVER_HOST=${SERVER_HOST:-"localhost"}

SERVER_USERNAME=${SERVER_USERNAME:-"qdrant"}

function run_exp() {
    SERVER_PATH=$1
    ENGINE_NAME=$2
    MONITOR_PATH=$(echo "$ENGINE_NAME" | sed -e 's/[^A-Za-z0-9._-]/_/g')
    ssh "${SERVER_USERNAME}@${SERVER_HOST}" "nohup bash -c 'cd ./projects/vector-db-benchmark/monitoring && rm -f docker.stats.jsonl && bash monitor_docker.sh' > /dev/null 2>&1 &"
    ssh -t "${SERVER_USERNAME}@${SERVER_HOST}" "cd ./projects/vector-db-benchmark/engine/servers/$SERVER_PATH ; docker compose down ; docker compose up -d"
    sleep 30
    python3 run.py --engines "$ENGINE_NAME" --datasets "${DATASETS}" --host "$SERVER_HOST"
    ssh -t "${SERVER_USERNAME}@${SERVER_HOST}" "cd ./projects/vector-db-benchmark/engine/servers/$SERVER_PATH ; docker compose down"
    ssh -t "${SERVER_USERNAME}@${SERVER_HOST}" "cd ./projects/vector-db-benchmark/monitoring && mkdir -p results && mv docker.stats.jsonl ./results/${MONITOR_PATH}-docker.stats.jsonl"
}


#run_exp "qdrant-single-node" 'qdrant-m-*'
run_exp "weaviate-single-node" 'weaviate-m-*'
run_exp "milvus-single-node" 'milvus-m-*'
run_exp "qdrant-single-node" 'qdrant-rps-m-*'


# run_exp "elasticsearch-single-node" 'elastic-m-*'
# run_exp "redis-single-node" 'redis-m-*'

# Extra: qdrant configured to tune RPS

