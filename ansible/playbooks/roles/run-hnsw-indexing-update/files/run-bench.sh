#!/bin/bash
# This script is used to set up a virtual environment, install dependencies, and run a Python script.

set -euo pipefail

if [ -z "${DATASET_DIM:-}" ]; then
    echo "Error: DATASET_DIM is not set"
    exit 1
fi

if [ -z "${BENCH:-}" ]; then
    echo "Error: BENCH is not set"
    exit 2
fi

if [ -z "${DATASET_NAME:-}" ]; then
    echo "Error: DATASET_NAME is not set"
    exit 3
fi


if [ -z "${OUTPUT_FILENAME:-}" ]; then
    echo "Error: OUTPUT_FILENAME is not set"
    exit 4
fi

if [ -z "${WORK_DIR:-}" ]; then
    WORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    echo "Warn: WORK_DIR is not set, defaults to script's ${WORK_DIR}"
fi

cd "${WORK_DIR}"

# Remove existing venv if present
if [ -d "${WORK_DIR}/venv" ]; then
    echo "Removing existing virtual environment..."
    rm -rf "${WORK_DIR}/venv"
fi

# Create and setup virtual environment
echo "Creating virtual environment..."
python3 -m venv "${WORK_DIR}/venv"

echo "Activating virtual environment..."
source "${WORK_DIR}/venv/bin/activate"

echo "Installing requirements..."
pip install -r "${WORK_DIR}/requirements.txt"

NOW=$(date "+%Y-%m-%dT%H:%M:%SZ")
echo "${NOW}"
echo "Running..."
python "${WORK_DIR}/${BENCH}.py"
echo "Python script completed with exit code: $?"
deactivate

exit 0