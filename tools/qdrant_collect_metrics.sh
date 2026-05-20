#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail
PHASE=$1   # "before" | "after"

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

source "$SCRIPT_PATH/ssh.sh"

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

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
  # Empty file → upload inserts NULL for fault columns (keeps RPS/p95 row).
  echo "warning: /metrics fetch failed (rc=$fetch_rc); writing empty placeholder" >&2
  : > "$out_file"
else
  echo "$RAW_METRICS" | grep -E '^process_(minor|major)_page_faults_total ' > "$out_file" || true
fi

set +e
CPU_TICKS=$(ssh_with_retry -tt -o ServerAliveInterval=10 -o ServerAliveCountMax=10 \
  "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" \
  "awk '{print \$14+\$15}' /proc/\$(pidof qdrant)/stat")
cpu_rc=$?
set -e
CPU_TICKS=$(echo "$CPU_TICKS" | tr -d '[:space:]')
if [[ $cpu_rc -eq 0 && -n "$CPU_TICKS" ]]; then
  echo "process_cpu_ticks_total ${CPU_TICKS}" >> "$out_file"
fi