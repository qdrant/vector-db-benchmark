#!/usr/bin/env bash

set -e

export DOCKER_VOLUME_DIRECTORY="/opt/vector-db-benchmark-volumes/"

# dataset as env variable or all
#DATASETS=${DATASETS:-"*"}
# selected dataset
DATASETS="europeana-all"

function run_exp() {
    SERVER_PATH=$1
    ENGINE_NAME=$2
    MONITOR_PATH=$(echo "$ENGINE_NAME" | sed -e 's/[^A-Za-z0-9._-]/_/g')
    nohup bash -c 'cd ./monitoring && rm -f docker.stats.jsonl && bash monitor_docker.sh' > /dev/null 2>&1 &
    cd ./engine/servers/$SERVER_PATH ; docker compose down ; docker compose up -d
    sleep 30
    cd - ; python3 run.py --engines "$ENGINE_NAME" --datasets "${DATASETS}"
    cd ./engine/servers/$SERVER_PATH ; docker compose down
    cd - && cd ./monitoring && mkdir -p results && mv docker.stats.jsonl ./results/${MONITOR_PATH}-docker.stats.jsonl
}


#run_exp "qdrant-single-node" 'qdrant-m-*'
#run_exp "weaviate-single-node" 'weaviate-m-*'
#run_exp "milvus-single-node-eu" 'milvus-m-16-*'
#run_exp "qdrant-single-node-eu" 'qdrant-m-16*'
#run_exp "redis-single-node-eu" 'redis-m-16*'
run_exp "elasticsearch-single-node-eu" 'elasticsearch-m-16-ef-128-eu'
#run_exp "redis-single-node" 'redis-m-*'
#run_exp "qdrant-single-node" 'qdrant-rps-m-*'


# run_exp "elasticsearch-single-node" 'elastic-m-*'
# run_exp "redis-single-node" 'redis-m-*'

# Extra: qdrant configured to tune RPS

