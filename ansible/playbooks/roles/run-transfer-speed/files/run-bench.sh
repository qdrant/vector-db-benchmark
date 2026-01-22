#!/bin/bash
set -euo pipefail
cd "${WORK_DIR:?}"
rm -rf venv && python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
python -u shard_transfer.py