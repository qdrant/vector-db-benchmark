#!/usr/bin/env bash

PROJECT_PATH=$(realpath "$(dirname "$0")/..")

rsync -avP --mkpath\
   "$PROJECT_PATH/engine/servers/" $1:./projects/vector-db-benchmark/engine/servers/
