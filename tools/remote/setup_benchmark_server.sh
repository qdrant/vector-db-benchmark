#!/bin/bash

set -e
set -x

VECTOR_DB=${VECTOR_DB:-qdrant}
BRANCH=${BRANCH:-master}

if [ -d "./vector-db-benchmark" ]; then
    echo "vector-db-benchmark repo already exists"
else
    git clone https://github.com/qdrant/vector-db-benchmark
fi

cd vector-db-benchmark
git fetch && git checkout $BRANCH && git pull

# remove all running containers:
RUNNING_CONTAINERS=$(docker ps -q)
if [ -n "$RUNNING_CONTAINERS" ]; then
    docker container rm -f $RUNNING_CONTAINERS
fi

if [ "$VECTOR_DB" == "qdrant" ] && [ "$QDRANT_VERSION" == "dev" ]; then
    docker rmi qdrant/qdrant:dev || true
fi

cd engine/servers/${VECTOR_DB}-single-node
docker compose up -d

# if vector DB is milvus or elasticsearch, wait for them to be up
if [ "$VECTOR_DB" == "milvus" ] || [ "$VECTOR_DB" == "elasticsearch" ]; then
    sleep 30 # Throws connection reset which isn't handled by --retry-connrefused in curl. So we need to wait
fi

# Define a map for database types and their health check URLs
declare -A db_health_urls
db_health_urls["milvus"]="http://localhost:19530/v1/vector/collections"
db_health_urls["qdrant"]="http://localhost:6333"
db_health_urls["elasticsearch"]="http://localhost:9200/_cluster/health"

# Check if the specified database type exists in the map
if [ -n "${db_health_urls[$VECTOR_DB]}" ]; then
    url="${db_health_urls[$VECTOR_DB]}"
    # Retry logic for the specified URL
    curl --max-time 120 --retry-connrefused --retry 10 --retry-delay 10 "$url"
else
    echo "Assuming engine $VECTOR_DB is already up"
fi
