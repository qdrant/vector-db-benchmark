#!/usr/bin/env bash

set -e

DATASETS=${DATASETS:-"*"}

SERVER_HOST=${SERVER_HOST:-"localhost"}

SERVER_USERNAME=${SERVER_USERNAME:-"qdrant"}

function run_exp() {
    SERVER_PATH=$1
    ENGINE_NAME=$2
    ssh -t ${SERVER_USERNAME}@${SERVER_HOST} "cd ./projects/vector-db-benchmark/engine/servers/$SERVER_PATH ; docker compose up -d"
    sleep 30
    python3 run.py --engines $ENGINE_NAME --datasets $DATASETS --host $SERVER_HOST
    ssh -t qdrant@$SERVER_HOST "cd ./projects/vector-db-benchmark/engine/servers/$SERVER_PATH ; docker compose down"
}


run_exp "qdrant-single-node" 'qdrant-m-*'
run_exp "weaviate-single-node" 'weaviate-m-*'
run_exp "milvus-single-node" 'milvus-m-*'
run_exp "elasticsearch-single-node" 'elastic-m-*'

# Extra: qdrant configured to tune RPS

run_exp "qdrant-single-node" 'qdrant-rps-m-*'
