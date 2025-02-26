#!/bin/bash

QDRANT_VERSION=${QDRANT_VERSION:-"ghcr/dev"}

#MAX_RETRIES=12
MAX_RETRIES=1

EVENT_TYPE="benchmark-trigger-image-build"

if [[ -z "${BEARER_TOKEN}" ]]; then
  echo "BEARER_TOKEN is not set. Exiting."
  exit 1
fi

# check if version starts with "docker" or "ghcr"
if [[ ${QDRANT_VERSION} == docker/* ]] || [[ ${QDRANT_VERSION} == ghcr/* ]]; then

    if [[ ${QDRANT_VERSION} == docker/* ]]; then
        # pull from docker hub
        QDRANT_VERSION=${QDRANT_VERSION#docker/}
        QDRANT_VERSION_IMG=${QDRANT_VERSION//\//-} # replace all / with -
        CONTAINER_REGISTRY='docker.io'
    elif [[ ${QDRANT_VERSION} == ghcr/* ]]; then
        # pull from github container registry
        QDRANT_VERSION=${QDRANT_VERSION#ghcr/}
        QDRANT_VERSION_IMG=${QDRANT_VERSION//\//-} # replace all / with -
        CONTAINER_REGISTRY='ghcr.io'
    fi
else
    echo "Error: unknown version ${QDRANT_VERSION}. Version name should start with 'docker/' or 'ghcr/'"
    exit 1
fi

IMAGE="${CONTAINER_REGISTRY}/qdrant/qdrant:${QDRANT_VERSION_IMG}"

if docker manifest inspect "$IMAGE" > /dev/null 2>&1; then
  echo "Image $IMAGE exists in the remote repository."
  exit 0
else
  echo "Image $IMAGE does not exist in the remote repository."
fi

if [[ "${CONTAINER_REGISTRY}" == "docker.io" ]]; then
  echo "Impossible to push the image to Docker Container Registry in this workflow."
  exit 1
fi

echo "Trigger image build for $IMAGE..."
curl -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${BEARER_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/qdrant/qdrant/dispatches \
  -d "{\"event_type\": \"$EVENT_TYPE\", \"client_payload\": {\"version\": \"$QDRANT_VERSION\", \"triggered\": true}}"

echo "Wait for the image to appear in the remote repository..."
counter=0
while ! docker manifest inspect "$IMAGE" > /dev/null 2>&1; do
  if [ $counter -ge $MAX_RETRIES ]; then
    echo "Reached maximum retries. Exiting."
    exit 2
  fi
  # sleep for 10 minutes, in seconds
  # together with the MAX_RETRIES it
  # will wait for 120 minutes
#  sleep 600
  sleep 60
  ((counter++))
done

echo "Image $IMAGE is now available in the remote repository."