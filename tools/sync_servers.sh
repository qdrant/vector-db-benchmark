#!/usr/bin/env bash

PROJECT_PATH=$(realpath "$(dirname "$0")/..")

max_retries=5
retry_delay=5
for ((i=1; i<=max_retries; i++)); do
    if rsync -e "ssh -o ConnectTimeout=30 -o ServerAliveInterval=10 -o ServerAliveCountMax=10" \
       -avP --mkpath "$PROJECT_PATH/engine/servers/" "$1:./projects/vector-db-benchmark/engine/servers/"; then
        break
    fi
    echo "rsync failed (attempt $i/$max_retries), retrying in ${retry_delay}s..."
    sleep $retry_delay
done
