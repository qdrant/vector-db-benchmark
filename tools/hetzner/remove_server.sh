#!/bin/bash

set -e

SERVER_NAME=${1:-}

if [ -z "$SERVER_NAME" ]; then
    echo "Server name is not provided"
    exit 1
fi

hcloud server delete "$SERVER_NAME"
