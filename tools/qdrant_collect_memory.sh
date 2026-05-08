#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

# Phase label ("before" / "after") — encoded in the output filename so the
# upload step can pair the two snapshots and compute the cache delta.
PHASE=$1

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}
COLLECTION_NAME=${COLLECTION_NAME:-"benchmark"}
QDRANT_CONTAINER_NAME=${QDRANT_CONTAINER_NAME:-"qdrant-continuous"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

source "$SCRIPT_PATH/ssh.sh"

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

# Qdrant per-collection memory/disk report. Captures total.disk_bytes,
# total.ram_bytes, total.cached_bytes, total.expected_cache_bytes — the
# "cached_bytes after search" is the direct proof of whether the working
# set is RAM-resident or actually on disk.
# Under a tight RAM cap, qdrant can return empty responses to this endpoint
# right after a heavy search (observed: curl exit 52 on inline-on 256m cells).
# Retry with backoff, and if it still fails write a stub JSON so the upload
# step inserts NULLs for the mem_* columns rather than dropping the cell.
set +e
REPORT=$(ssh_with_retry -tt -o ServerAliveInterval=10 -o ServerAliveCountMax=10 \
  "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" \
  "curl -s --retry 5 --retry-delay 5 --retry-all-errors --max-time 30 \
       http://localhost:6333/collections/${COLLECTION_NAME}/memory")
mem_rc=$?
set -e

CURRENT_DATE=$(date +%Y-%m-%d-%H-%M-%S)
mkdir -p results
out_file=results/qdrant-memory-"${PHASE}"-"${CURRENT_DATE}".json
if [[ $mem_rc -ne 0 || -z "$REPORT" ]]; then
  echo "warning: /collections/${COLLECTION_NAME}/memory fetch failed (rc=$mem_rc); writing empty placeholder" >&2
  echo '{}' > "$out_file"
else
  echo "$REPORT" > "$out_file"
fi

set +e
CGROUP_CURRENT=$(ssh_with_retry -tt -o ServerAliveInterval=10 -o ServerAliveCountMax=10 \
  "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" \
  "docker exec ${QDRANT_CONTAINER_NAME} cat /sys/fs/cgroup/memory.current 2>/dev/null || echo 0")
cg_rc=$?
set -e
CGROUP_CURRENT=$(echo "$CGROUP_CURRENT" | tr -dc '0-9')

cgroup_file=results/qdrant-cgroup-current-"${PHASE}"-"${CURRENT_DATE}".txt
if [[ $cg_rc -ne 0 || -z "$CGROUP_CURRENT" ]]; then
  echo "warning: cgroup memory.current fetch failed (rc=$cg_rc)" >&2
  : > "$cgroup_file"
else
  echo "$CGROUP_CURRENT" > "$cgroup_file"
fi