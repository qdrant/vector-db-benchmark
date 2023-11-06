#!/bin/bash

# Usage: tools/ssh.sh custom|hetzner <server-name>

set -e

SCRIPT_PATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
CLOUD_NAME=${CLOUD_NAME:-$1}

SERVER_NAME=${SERVER_NAME:-$2}

DEFAULT_SSH_USER=$(bash $SCRIPT_PATH/$CLOUD_NAME/get_ssh_user.sh $SERVER_NAME)
SSH_USER=${SSH_USER:-${DEFAULT_SSH_USER}}

if [[ -z "$CLOUD_NAME" ]]
then
    echo "Please pass CLOUD_NAME env variable"
    exit 1
fi

if [[ -z "$SERVER_NAME" ]]
then
    echo "Please specify SERVER_NAME env variable"
    exit 1
fi

# Get server ip
SERVER_IP=$(bash $SCRIPT_PATH/$CLOUD_NAME/get_public_ip.sh $SERVER_NAME)

ssh $SSH_USER@$SERVER_IP
