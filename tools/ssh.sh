#!/bin/bash

# Usage: tools/ssh.sh custom|hetzner <server-name>
# Can also be sourced to use ssh_with_retry/scp_with_retry functions

# Helper function: SSH with retry logic
# Usage: ssh_with_retry [ssh_options...] user@host command
# Only retries on connection errors (exit code 255), not command failures
ssh_with_retry() {
    local max_retries=${SSH_MAX_RETRIES:-5}
    local retry_delay=${SSH_RETRY_DELAY:-5}
    local exit_code
    local i

    for ((i=1; i<=max_retries; i++)); do
        ssh -o ConnectTimeout=10 "$@"
        exit_code=$?
        if [[ $exit_code -eq 0 ]]; then
            return 0
        fi
        # Only retry on connection errors (255), not remote command failures
        if [[ $exit_code -ne 255 ]]; then
            return $exit_code
        fi
        if [[ $i -lt $max_retries ]]; then
            echo "SSH connection failed (attempt $i/$max_retries), retrying in ${retry_delay}s..." >&2
            sleep $retry_delay
        fi
    done

    echo "SSH failed after $max_retries attempts" >&2
    return 255
}

# Helper function: SCP with retry logic
# Usage: scp_with_retry [scp_options...] source destination
# Only retries on connection errors (exit code 255), not file errors
scp_with_retry() {
    local max_retries=${SSH_MAX_RETRIES:-5}
    local retry_delay=${SSH_RETRY_DELAY:-5}
    local exit_code
    local i

    for ((i=1; i<=max_retries; i++)); do
        scp -o ConnectTimeout=10 "$@"
        exit_code=$?
        if [[ $exit_code -eq 0 ]]; then
            return 0
        fi
        # Only retry on connection errors (255), not file/permission errors
        if [[ $exit_code -ne 255 ]]; then
            return $exit_code
        fi
        if [[ $i -lt $max_retries ]]; then
            echo "SCP connection failed (attempt $i/$max_retries), retrying in ${retry_delay}s..." >&2
            sleep $retry_delay
        fi
    done

    echo "SCP failed after $max_retries attempts" >&2
    return 255
}

# Helper function: rsync with retry logic
# Usage: rsync_with_retry [rsync_options...] source destination
# Note: Uses RSYNC_RSH env var if set, otherwise uses sensible defaults
# Only retries on network/connection errors, not file/syntax errors
rsync_with_retry() {
    local max_retries=${SSH_MAX_RETRIES:-5}
    local retry_delay=${SSH_RETRY_DELAY:-5}
    local exit_code
    local i
    local rsync_rsh="${RSYNC_RSH:-ssh -o ConnectTimeout=30 -o ServerAliveInterval=10 -o ServerAliveCountMax=10}"

    for ((i=1; i<=max_retries; i++)); do
        RSYNC_RSH="$rsync_rsh" rsync "$@"
        exit_code=$?
        if [[ $exit_code -eq 0 ]]; then
            return 0
        fi
        # Only retry on network-related errors:
        # 12 = error in rsync protocol data stream (network issue)
        # 255 = SSH connection error
        if [[ $exit_code -ne 12 && $exit_code -ne 255 ]]; then
            return $exit_code
        fi
        if [[ $i -lt $max_retries ]]; then
            echo "rsync connection failed (attempt $i/$max_retries), retrying in ${retry_delay}s..." >&2
            sleep $retry_delay
        fi
    done

    echo "rsync failed after $max_retries attempts" >&2
    return $exit_code
}

# Only run interactive SSH if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    set -e

    SCRIPT_PATH="$( cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"
    CLOUD_NAME=${CLOUD_NAME:-$1}

    SERVER_NAME=${SERVER_NAME:-$2}

    if [[ -z "$CLOUD_NAME" ]]; then
        echo "Please pass CLOUD_NAME env variable"
        exit 1
    fi

    if [[ -z "$SERVER_NAME" ]]; then
        echo "Please specify SERVER_NAME env variable"
        exit 1
    fi

    DEFAULT_SSH_USER=$(bash "$SCRIPT_PATH/$CLOUD_NAME/get_ssh_user.sh" "$SERVER_NAME")
    SSH_USER=${SSH_USER:-${DEFAULT_SSH_USER}}

    # Get server ip
    SERVER_IP=$(bash "$SCRIPT_PATH/$CLOUD_NAME/get_public_ip.sh" "$SERVER_NAME")

    ssh "$SSH_USER@$SERVER_IP"
fi
