#!/bin/bash

set -e

CLOUD_NAME=${CLOUD_NAME:-"hetzner"}
SERVER_USERNAME=${SERVER_USERNAME:-"root"}

SCRIPT=$(realpath "$0")
SCRIPT_PATH=$(dirname "$SCRIPT")

BENCH_SERVER_NAME=${SERVER_NAME:-"benchmark-server-1"}

IP_OF_THE_CLEINT=$(bash "${SCRIPT_PATH}/${CLOUD_NAME}/get_public_ip.sh" "$BENCH_SERVER_NAME")
