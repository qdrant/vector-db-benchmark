#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

# Phase label ("before" / "after") — encoded in the output filename so the
# upload step can pair the two snapshots and compute deltas.
PHASE=$1

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

source "$SCRIPT_PATH/ssh.sh"

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

# Pull /metrics raw with curl retries (qdrant under a tight RAM cap can drop
# the first connection right after a heavy search). Filter to the prom counters
# we care about on the runner side so an empty response doesn't crash the
# remote pipeline with grep exit 1.
set +e
RAW_METRICS=$(ssh_with_retry -tt -o ServerAliveInterval=10 -o ServerAliveCountMax=10 \
  "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" \
  "curl -s --retry 5 --retry-delay 5 --retry-all-errors --max-time 30 http://localhost:6333/metrics")
fetch_rc=$?
set -e

CURRENT_DATE=$(date +%Y-%m-%d-%H-%M-%S)
mkdir -p results
out_file=results/qdrant-metrics-"${PHASE}"-"${CURRENT_DATE}".txt
if [[ $fetch_rc -ne 0 || -z "$RAW_METRICS" ]]; then
  # Write an empty file so the upload step sees no values and inserts NULLs for
  # page-fault columns. Losing this signal is worse than dropping the cell, but
  # dropping the cell loses RPS/p95 too — net it's still a win to upload.
  echo "warning: /metrics fetch failed (rc=$fetch_rc); writing empty placeholder" >&2
  : > "$out_file"
else
  echo "$RAW_METRICS" | grep -E '^process_(minor|major)_page_faults_total ' > "$out_file" || true
fi