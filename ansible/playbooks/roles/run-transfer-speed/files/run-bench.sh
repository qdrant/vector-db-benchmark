#!/bin/bash
set -euo pipefail

: "${QDRANT_URIS:?QDRANT_URIS is required}"
: "${DATASET_NAME:?DATASET_NAME is required}"
: "${OUTPUT_FILENAME:?OUTPUT_FILENAME is required}"
: "${WORK_DIR:?WORK_DIR is required}"

RUNS="${RUNS:-3}"

cd "${WORK_DIR}"

rm -rf "${WORK_DIR}/venv"
python3 -m venv "${WORK_DIR}/venv"
source "${WORK_DIR}/venv/bin/activate"
pip install -q -r "${WORK_DIR}/requirements.txt"

python -u "${WORK_DIR}/shard_transfer.py"

deactivate