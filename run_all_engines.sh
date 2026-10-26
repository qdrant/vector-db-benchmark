#!/usr/bin/env bash
# Green-field HNSW grid: m={16,32,64} × ef_construct={100,200,500,1000}.
# Search uses the same ef values at parallel 1 (latency) and 100 (RPS).

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DATASETS=${DATASETS:-"glove-100-angular,gist-960-euclidean,dbpedia-openai-1M-1536-angular,cohere-wiki-1m"}

# FineWeb is optional (nice-to-have). The published report is glove / gist /
# dbpedia / cohere. Set RUN_FINEWEB=1 to append FineWeb-1M after that core grid.
if [[ "${RUN_FINEWEB:-0}" == "1" && -n "${FINEWEB_10B_DIR:-}" && ",${DATASETS}," != *",fineweb-"* ]]; then
    DATASETS="${DATASETS},${FINEWEB_DATASETS:-fineweb-10b-dense-1m}"
fi

grid_names() {
    local engine=$1
    local names=() m ef
    for m in 16 32 64; do
        for ef in 100 200 500 1000; do
            names+=("${engine}-m-${m}-ef-${ef}")
        done
    done
    local IFS=','
    echo "${names[*]}"
}

"${ROOT_DIR}/tools/run_local_engine.sh" "qdrant-single-node" "$(grid_names qdrant)" "$DATASETS"
"${ROOT_DIR}/tools/run_local_engine.sh" "weaviate-single-node" "$(grid_names weaviate)" "$DATASETS"
"${ROOT_DIR}/tools/run_local_engine.sh" "milvus-single-node" "$(grid_names milvus)" "$DATASETS"
"${ROOT_DIR}/tools/run_local_engine.sh" "elasticsearch-single-node" "$(grid_names elasticsearch)" "$DATASETS"
"${ROOT_DIR}/tools/run_local_engine.sh" "opensearch-single-node" "$(grid_names opensearch)" "$DATASETS"
"${ROOT_DIR}/tools/run_local_engine.sh" "redis-single-node" "$(grid_names redis)" "$DATASETS"
"${ROOT_DIR}/tools/run_local_engine.sh" "pgvector-single-node" "$(grid_names pgvector)" "$DATASETS"
