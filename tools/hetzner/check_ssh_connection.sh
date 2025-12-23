#!/bin/bash

set -e

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"

SERVER_NAME=${SERVER_NAME:-test-server-1}

SERVER_IP=$(bash "$SCRIPT_PATH/get_public_ip.sh" "${SERVER_NAME}")

echo "Server IP: ${SERVER_IP}"

ssh-keygen -f "$HOME/.ssh/known_hosts" -R "${SERVER_IP}" || true

max_retries=10
retry_delay=2

for ((i=1; i<=max_retries; i++)); do
    if ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "root@${SERVER_IP}" echo "Server is ready"; then
        exit 0
    fi
    echo "SSH connection failed (attempt $i/$max_retries), retrying in ${retry_delay}s..."
    sleep $retry_delay
done

echo "Failed to establish SSH connection after $max_retries attempts"
exit 1
