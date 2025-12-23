#!/usr/bin/env bash

set -e

SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)"
PROJECT_PATH="$(realpath "$SCRIPT_PATH/..")"

if [[ -z "$1" ]]; then
    echo "Usage: $0 user@host" >&2
    exit 1
fi

source "$SCRIPT_PATH/ssh.sh"

rsync_with_retry -avP --mkpath "$PROJECT_PATH/engine/servers/" "$1:./projects/vector-db-benchmark/engine/servers/"
