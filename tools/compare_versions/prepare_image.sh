#!/bin/bash

QDRANT_VERSION=${QDRANT_VERSION:-"ghcr/dev"}

#MAX_RETRIES=12
MAX_RETRIES=1

# check if version starts with "docker" or "ghcr"
if [[ ${QDRANT_VERSION} == docker/* ]] || [[ ${QDRANT_VERSION} == ghcr/* ]]; then

    if [[ ${QDRANT_VERSION} == docker/* ]]; then
        # pull from docker hub
        QDRANT_VERSION=${QDRANT_VERSION#docker/}
        CONTAINER_REGISTRY='docker.io'
    elif [[ ${QDRANT_VERSION} == ghcr/* ]]; then
        # pull from github container registry
        QDRANT_VERSION=${QDRANT_VERSION#ghcr/}
        CONTAINER_REGISTRY='ghcr.io'
    fi
else
    echo "Error: unknown version ${QDRANT_VERSION}. Version name should start with 'docker/' or 'ghcr/'"
    exit 1
fi

IMAGE="${CONTAINER_REGISTRY}/qdrant/qdrant:${QDRANT_VERSION}"

if docker manifest inspect "$IMAGE" > /dev/null 2>&1; then
  echo "Image $IMAGE exists in the remote repository."
  exit 0
else
  echo "Image $IMAGE does not exist in the remote repository."
fi

# TODO: add logic to trigger image build in qdrant repo

echo "Waiting for the image to appear in the remote repository..."
counter=0
while ! docker manifest inspect "$IMAGE" > /dev/null 2>&1; do
  if [ $counter -ge $MAX_RETRIES ]; then
    echo "Reached maximum retries. Exiting."
    exit 1
  fi
  # sleep for 10 minutes, in seconds
  # together with the MAX_RETRIES it
  # will wait for 120 minutes
  sleep 600
  ((counter++))
done

echo "Image $IMAGE is now available in the remote repository."