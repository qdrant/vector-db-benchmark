#!/bin/bash

set -e
# Get ip of the private network interface of custom cloud server

# Usage: ./get_private_ip.sh <server_name>

# Example: ./get_private_ip.sh benchmark-server-1


SCRIPT=$(realpath "$0")
SCRIPTPATH=$(dirname "$SCRIPT")

SSH_USER=$(jq ".[\"${1}\"].user" -r $SCRIPTPATH/data.json)

echo "${SSH_USER}"
