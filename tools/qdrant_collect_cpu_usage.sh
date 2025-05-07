#!/bin/bash

PS4='ts=$(date "+%Y-%m-%dT%H:%M:%SZ") level=DEBUG line=$LINENO file=$BASH_SOURCE '
set -euo pipefail

# Examples: start or end
MODE=$1

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

IP_OF_THE_SERVER=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")

UTIME=$(ssh -tt -o ServerAliveInterval=10 -o ServerAliveCountMax=10 "${SERVER_USERNAME}@${IP_OF_THE_SERVER}" "cat /proc/\$(pidof qdrant)/stat | awk '{print \$14}'")
# Clean up any whitespace characters
UTIME=$(echo "$UTIME" | tr -d '[:space:]')

CURRENT_DATE=$(date +%Y-%m-%d-%H-%M-%S)

mkdir -p results/cpu

if [[ "$MODE" == "end" ]]; then
  echo "Calculate CPU usage (seconds) over period of time"
  UTIME_FILE=$(ls -t results/cpu/utime-*.txt | head -n 1)
  UTIME_START=$(cat "$UTIME_FILE" | tr -d '[:space:]')
  echo "$UTIME" >> "${UTIME_FILE}"
  CPU=$(echo "scale=2; ($UTIME - $UTIME_START) / 100" | bc)
  echo "$CPU" > "./results/cpu/cpu-usage-${CURRENT_DATE}.txt"
elif [[ "$MODE" == "start" ]]; then
  echo "Store utime start value in ./results/cpu/utime-${CURRENT_DATE}.txt"
  echo "$UTIME" > "./results/cpu/utime-${CURRENT_DATE}.txt"
else
  echo "Unknown mode: $MODE"
  exit 1
fi
