#!/usr/bin/env bash

PROJECT_PATH=$(realpath "$(dirname "$0")/..")

rsync -avP \
   --exclude="results" \
   --exclude="results-*" \
   --exclude='*.hdf5' \
   --exclude='venv' \
   --exclude='__pycache__' \
   --exclude='frontend' \
   --exclude='.idea' \
   --exclude='.git' \
   --exclude='datasets/*/' \
   "$PROJECT_PATH/" $1:./projects/vector-db-benchmark/
