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


max_retries=${HCLOUD_MAX_RETRIES:-5}
retry_delay=${HCLOUD_RETRY_DELAY:-5}

for ((i=1; i<=max_retries; i++)); do
    if hcloud server create \
        --name "${SERVER_NAME}" \
        --type "${SERVER_TYPE}" \
        --image "${SERVER_IMAGE}" \
        --location "${SERVER_LOCATION}" \
        --ssh-key "${SERVER_SSH_KEY}" \
        --network "${SERVER_NETWORK}"; then
        break
    fi
    if [[ $i -lt $max_retries ]]; then
        echo "hcloud server create failed (attempt $i/$max_retries), retrying in ${retry_delay}s..." >&2
        sleep $retry_delay
    else
        echo "hcloud server create failed after $max_retries attempts" >&2
        exit 1
    fi
done

# Get server IP
SERVER_IP=$(bash "${SCRIPTPATH}/get_public_ip.sh" "${SERVER_NAME}")

echo "Server IP: ${SERVER_IP}"

ssh-keygen -f "$HOME/.ssh/known_hosts" -R "${SERVER_IP}" || true

# Wait for server to be ready

while ! ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "root@${SERVER_IP}" echo "Server is ready"; do
    sleep 1
done

# Create and install docker

cat "${SCRIPTPATH}/setup_hetzner.sh" | ssh -o ConnectTimeout=10 "root@${SERVER_IP}" bash
