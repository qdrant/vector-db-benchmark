#!/bin/bash

set -e

# path relative to the script

SCRIPT=$(realpath "$0")
SCRIPTPATH=$(dirname "$SCRIPT")


# Create server in custom Cloud

SERVER_NAME=${SERVER_NAME:-test-server-1}


SERVER_IP=$(jq ".[\"${SERVER_NAME}\"].public_ip" -r $SCRIPTPATH/data.json)

SSH_USER=$(jq ".[\"${SERVER_NAME}\"].user" -r $SCRIPTPATH/data.json)

echo "Server IP: ${SERVER_IP}"

ssh-keygen -f "$HOME/.ssh/known_hosts" -R "${SERVER_IP}" || true

# Wait for server to be ready

while ! ssh -oStrictHostKeyChecking=no ${SSH_USER}@${SERVER_IP} echo "Server is ready"; do
    sleep 1
done

# Create and install docker, poetry, etc

cat "${SCRIPTPATH}/setup_vm.sh" | ssh "${SSH_USER}@${SERVER_IP}" sudo bash
