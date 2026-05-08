#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

source "$SCRIPT_PATH/ssh.sh"

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

# Poll /readyz until Qdrant is fully up. Required after a phase-2 container
# restart with a tight memory cap (e.g. 96m): the next call hits /metrics and
# `grep -E '^process_…'` returns 1 on an empty body, ssh_with_retry treats
# that as a non-connection failure (no retry), and the whole cell aborts.
TIMEOUT_S=${QDRANT_READY_TIMEOUT_S:-180}
INTERVAL_S=${QDRANT_READY_INTERVAL_S:-2}

elapsed=0
while true; do
  http_code=$(ssh -o ConnectTimeout=10 -o ServerAliveInterval=10 \
    "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" \
    "curl -s -o /dev/null -w '%{http_code}' http://localhost:6333/readyz" \
    2>/dev/null || true)
  if [[ "$http_code" == "200" ]]; then
    echo "Qdrant ready after ${elapsed}s"
    exit 0
  fi
  if (( elapsed >= TIMEOUT_S )); then
    echo "Timeout: Qdrant /readyz still ${http_code:-<no-response>} after ${TIMEOUT_S}s"
    exit 1
  fi
  echo "  ... waiting for Qdrant /readyz (got ${http_code:-<no-response>}, ${elapsed}s elapsed)"
  sleep "$INTERVAL_S"
  elapsed=$((elapsed + INTERVAL_S))
done