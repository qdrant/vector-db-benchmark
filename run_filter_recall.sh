#!/usr/bin/env bash
# Filter-recall suite on the same HNSW grid: m={16,32,64} × ef_construct={100,200,500,1000}.

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
DATASETS=${DATASETS:-"random-match-keyword-100-angular-filters,random-match-keyword-100-angular-no-filters,random-match-int-100-angular-filters,random-match-int-100-angular-no-filters,random-range-100-angular-filters,random-range-100-angular-no-filters,random-geo-radius-100-angular-filters,random-geo-radius-100-angular-no-filters,arxiv-titles-384-angular-filters,arxiv-titles-384-angular-no-filters,h-and-m-2048-angular-filters,h-and-m-2048-angular-no-filters"}

if [[ -n "${FINEWEB_10B_DIR:-}" && ",${DATASETS}," != *",fineweb-"* ]]; then
    DATASETS="${DATASETS},${FINEWEB_FILTER_DATASETS:-fineweb-10b-dense-text-filters,fineweb-10b-dense-structured-filters}"
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
