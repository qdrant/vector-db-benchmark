#!/bin/bash

set -e

# path relative to the script

SCRIPT=$(realpath "$0")
SCRIPTPATH=$(dirname "$SCRIPT")


# Create server in Hetzner Cloud

SERVER_NAME=${SERVER_NAME:-test-server-1}

SERVER_TYPE=${SERVER_TYPE:-cx41}

SERVER_IMAGE=${SERVER_IMAGE:-ubuntu-22.04}

SERVER_LOCATION=${SERVER_LOCATION:-fsn1}

SERVER_SSH_KEY=${SERVER_SSH_KEY:-'benchmark@qdrant.tech'}

SERVER_NETWORK=${SERVER_NETWORK:-'benchmarks'}


hcloud server create \
    --name "${SERVER_NAME}" \
    --type "${SERVER_TYPE}" \
    --image "${SERVER_IMAGE}" \
    --location "${SERVER_LOCATION}" \
    --ssh-key "${SERVER_SSH_KEY}" \
    --network "${SERVER_NETWORK}"

# Get server IP
SERVER_IP=$(hcloud server ip "${SERVER_NAME}")

echo "Server IP: ${SERVER_IP}"

ssh-keygen -f "$HOME/.ssh/known_hosts" -R "${SERVER_IP}" || true

# Wait for server to be ready

while ! ssh -oStrictHostKeyChecking=no root@${SERVER_IP} echo "Server is ready"; do
    sleep 1
done

# Create and install docker

cat "${SCRIPTPATH}/setup_hetzner.sh" | ssh "root@${SERVER_IP}" bash
