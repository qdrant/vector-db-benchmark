#!/bin/bash

# Usage: tools/run_benchmarks.sh "deep-image-96-angular" "new-benchmark-server"

set -e
set -x

SCRIPT_PATH="$( cd "$(dirname "$0")" &>/dev/null ; pwd -P )"
export CLOUD_NAME=${CLOUD_NAME:-"custom"}

DATASETS=("glove-100-angular" "deep-image-96" "gist-960-euclidean" "dbpedia-openai-1M-1536-angular")
VECTOR_DBS=("qdrant" "milvus" "elasticsearch" "weaviate" "redis")
BRANCH="master"

# Note: If you want to run with a different version of Qdrant. Set the QDRANT_VERSION env variable.
# export QDRANT_VERSION=dev

# Run only while setting up new benchmark server and client:
# Create different servers and clients for each dataset so benchmarking can be done in parallel
# for dataset in "${DATASETS[@]}"; do
#     SERVER_NAME=benchmark-client-${dataset} bash -x $SCRIPT_PATH/$CLOUD_NAME/create_and_install.sh
#     SERVER_NAME=benchmark-server-${dataset} bash -x $SCRIPT_PATH/$CLOUD_NAME/create_and_install.sh
# done

DATASET=$1
SERVER_NAME=$2

# replace "server" with "client" if 3rd argument is not passed
CLIENT_NAME=${3:-"${SERVER_NAME/server/client}"}
PRIVATE_SERVER_IP=$(bash $SCRIPT_PATH/$CLOUD_NAME/get_private_ip.sh $SERVER_NAME)

for VECTOR_DB in "${VECTOR_DBS[@]}"; do
    echo Running benchmark for ${VECTOR_DB} on ${DATASET}

    RUN_SCRIPT="${SCRIPT_PATH}/remote/setup_benchmark_server.sh" \
        ENV_CONTEXT="${VECTOR_DB@A} ${BRANCH@A} ${QDRANT_VERSION@A}" \
        SERVER_NAME=${SERVER_NAME} \
        bash -x $SCRIPT_PATH/run_remote.sh

    RUN_SCRIPT="${SCRIPT_PATH}/remote/setup_benchmark_client.sh" \
        ENV_CONTEXT="${VECTOR_DB@A} ${BRANCH@A} ${PRIVATE_SERVER_IP@A} ${DATASET@A}" \
        SERVER_NAME=${CLIENT_NAME} \
        bash -x $SCRIPT_PATH/run_remote.sh
done
