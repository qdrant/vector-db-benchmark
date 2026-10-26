#!/usr/bin/env bash
# Resolve the Python used by the local benchmark client.
# Prefers the conda env named "benchmark".

if [[ -n "${BENCHMARK_PYTHON:-}" && -x "${BENCHMARK_PYTHON}" ]]; then
    :
elif [[ -x "${CONDA_PREFIX:-}/envs/benchmark/bin/python" ]]; then
    BENCHMARK_PYTHON="${CONDA_PREFIX}/envs/benchmark/bin/python"
elif [[ -x /home/ubuntu/opt/miniconda3/envs/benchmark/bin/python ]]; then
    BENCHMARK_PYTHON=/home/ubuntu/opt/miniconda3/envs/benchmark/bin/python
elif command -v conda >/dev/null 2>&1; then
    BENCHMARK_PYTHON=$(conda run -n benchmark which python 2>/dev/null || true)
fi

if [[ -z "${BENCHMARK_PYTHON:-}" || ! -x "${BENCHMARK_PYTHON}" ]]; then
    echo "conda env 'benchmark' not found; set BENCHMARK_PYTHON" >&2
    exit 1
fi

export BENCHMARK_PYTHON
export PYTHONPATH="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}${PYTHONPATH:+:${PYTHONPATH}}"

export BENCHMARK_HOME="${BENCHMARK_HOME:-/mnt/benchmark}"
export BENCHMARK_DATASETS_DIR="${BENCHMARK_DATASETS_DIR:-${BENCHMARK_HOME}/datasets}"
export BENCHMARK_RESULTS_DIR="${BENCHMARK_RESULTS_DIR:-${BENCHMARK_HOME}/results}"
export BENCHMARK_MONITORING_DIR="${BENCHMARK_MONITORING_DIR:-${BENCHMARK_HOME}/monitoring}"
export FINEWEB_QUERY_DIR="${FINEWEB_QUERY_DIR:-${BENCHMARK_HOME}/fineweb}"
if [[ -f "${FINEWEB_QUERY_DIR}/bf_k1000_parsed_ids.parquet" ]]; then
    export FINEWEB_QUERY_VECTORS="${FINEWEB_QUERY_VECTORS:-${FINEWEB_QUERY_DIR}/bf_k1000_parsed_ids.parquet}"
fi
mkdir -p "$BENCHMARK_DATASETS_DIR" "$BENCHMARK_RESULTS_DIR" "$BENCHMARK_MONITORING_DIR"
