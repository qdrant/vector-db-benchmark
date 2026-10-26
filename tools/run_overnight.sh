#!/usr/bin/env bash
# Full green-field grid. Datasets, results, and docker stats stay under BENCHMARK_HOME.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
export BENCHMARK_HOME="${BENCHMARK_HOME:-/mnt/benchmark}"
# Prefer a locally staged 1M shard so S3 token expiry cannot abort FineWeb.
if [[ -z "${FINEWEB_10B_DIR:-}" ]]; then
    if [[ -d "${BENCHMARK_HOME}/fineweb/corpus" ]]; then
        FINEWEB_10B_DIR="${BENCHMARK_HOME}/fineweb/corpus"
    else
        FINEWEB_10B_DIR=/home/ubuntu/data/fineweb
    fi
fi
export FINEWEB_10B_DIR
export FINEWEB_QUERY_DIR="${FINEWEB_QUERY_DIR:-${BENCHMARK_HOME}/fineweb}"
export RUN_PY_ARGS="${RUN_PY_ARGS:---skip-if-exists --no-exit-on-error}"

# shellcheck source=python_env.sh
source "${ROOT_DIR}/tools/python_env.sh"

mkdir -p \
    "$BENCHMARK_DATASETS_DIR" \
    "$BENCHMARK_RESULTS_DIR" \
    "$BENCHMARK_MONITORING_DIR/results" \
    "${BENCHMARK_HOME}/logs"

if [[ ! -f "${BENCHMARK_DATASETS_DIR}/datasets.json" ]]; then
    cp "${ROOT_DIR}/datasets/datasets.json" "${BENCHMARK_DATASETS_DIR}/datasets.json"
fi
if [[ ! -e "${BENCHMARK_DATASETS_DIR}/random-100" && -d "${ROOT_DIR}/datasets/random-100" ]]; then
    ln -s "${ROOT_DIR}/datasets/random-100" "${BENCHMARK_DATASETS_DIR}/random-100"
fi

echo "BENCHMARK_HOME=${BENCHMARK_HOME}"
echo "DATASETS_DIR=${BENCHMARK_DATASETS_DIR}"
echo "RESULTS_DIR=${BENCHMARK_RESULTS_DIR}"
echo "PYTHON=${BENCHMARK_PYTHON}"
echo "FINEWEB_10B_DIR=${FINEWEB_10B_DIR}"
echo "FINEWEB_QUERY_DIR=${FINEWEB_QUERY_DIR}"

cd "$ROOT_DIR"
for dataset in glove-100-angular gist-960-euclidean dbpedia-openai-1M-1536-angular cohere-wiki-1m; do
    echo "======== DOWNLOAD ${dataset} ========"
    "${BENCHMARK_PYTHON}" - <<PY
from benchmark.config_read import read_dataset_config
from benchmark.dataset import Dataset

Dataset(read_dataset_config()["${dataset}"]).download()
PY
done

echo "======== CORE GRID (Wednesday report): glove, gist, dbpedia, cohere ========"
DATASETS="glove-100-angular,gist-960-euclidean,dbpedia-openai-1M-1536-angular,cohere-wiki-1m" \
    RUN_FINEWEB=0 \
    "${ROOT_DIR}/run_all_engines.sh"

echo "======== FINEWEB APPENDIX (after the core report) ========"
DATASETS="${FINEWEB_DATASETS:-fineweb-10b-dense-1m}" \
    RUN_FINEWEB=1 \
    "${ROOT_DIR}/run_all_engines.sh"
