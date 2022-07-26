#!/bin/bash

cd "$(dirname "$0")/../../"


ENGINE_NAME="weaviate-1.14.1"
DATASET_NAME="random-100"
SERVER_BACKEND="remote"
CLIENT_BACKEND="remote"
SERVER_HOST="49.12.245.80"
DOCKER_HOST="ssh://benchmark"

venv/bin/python3 main.py run-server $ENGINE_NAME \
  --backend-type $SERVER_BACKEND \
  --docker-host $DOCKER_HOST