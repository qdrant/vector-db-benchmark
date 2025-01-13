#!/usr/bin/env bash

PROJECT_PATH=$(realpath "$(dirname "$0")/..")

rsync -e "ssh -o ServerAliveInterval=10 -o ServerAliveCountMax=10" -avP --mkpath\
   "$PROJECT_PATH/engine/servers/" $1:./projects/vector-db-benchmark/engine/servers/
