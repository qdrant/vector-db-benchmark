#!/bin/bash

SERVER_NAME=${SERVER_NAME:-test-server-1}

SERVER_IP=$(hcloud server ip "${SERVER_NAME}")

echo "Server IP: ${SERVER_IP}"

ssh-keygen -f "$HOME/.ssh/known_hosts" -R "${SERVER_IP}" || true

ssh -oStrictHostKeyChecking=no root@${SERVER_IP} echo "Server is ready"
