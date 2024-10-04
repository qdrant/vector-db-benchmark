#!/usr/bin/env bash

set -e
set DOCKER_VOLUME_DIRECTORY=/opt/milvus-single-node-eu/
#DATASETS="random-100"
DATASETS="europeana-all"
#all milvus m-16
ENGINE_NAME="milvus-m-16-*"
#all redis m-16
#ENGINE_NAME="redis-m-16-*"
#all qdrant m-16
#ENGINE_NAME="qdrant-m-16-*"
#all milvus
#ENGINE_NAME="milvus-m-*"

python3 run.py --engines "$ENGINE_NAME" --datasets "${DATASETS}"


