#!/bin/bash

set -e
# Get ip of the private network interface of Hetzner server
# Using `hcloud` CLI tool

# Usage: ./get_private_ip.sh <server_name>

# Example: ./get_private_ip.sh benchmark-server-1

max_retries=${HCLOUD_MAX_RETRIES:-5}
retry_delay=${HCLOUD_RETRY_DELAY:-5}

for ((i=1; i<=max_retries; i++)); do
    if result=$(hcloud server describe "$1" -o json 2>&1); then
        echo "$result" | jq -r '.private_net[0].ip'
        exit 0
    fi
    if [[ $i -lt $max_retries ]]; then
        echo "hcloud failed (attempt $i/$max_retries), retrying in ${retry_delay}s..." >&2
        sleep $retry_delay
    fi
done

echo "hcloud failed after $max_retries attempts: $result" >&2
exit 1
