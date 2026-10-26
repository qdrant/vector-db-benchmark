#!/usr/bin/env bash
# One HNSW cell (m=16, ef_construct=100) against one dataset, every engine.
# Intended as a pre-flight before the overnight grid.

set -u

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DATASET=${1:-${DATASETS:-random-100}}
CELL=${CELL:-m-16-ef-100}

engines=(
    "qdrant-single-node:qdrant"
    "weaviate-single-node:weaviate"
    "milvus-single-node:milvus"
    "elasticsearch-single-node:elasticsearch"
    "opensearch-single-node:opensearch"
    "redis-single-node:redis"
    "pgvector-single-node:pgvector"
)

passed=()
failed=()

for spec in "${engines[@]}"; do
    compose=${spec%%:*}
    engine=${spec##*:}
    echo "======== SMOKE ${engine}-${CELL} / ${DATASET} ========"
    if "${ROOT_DIR}/tools/run_local_engine.sh" "$compose" "${engine}-${CELL}" "$DATASET"; then
        passed+=("$engine")
        echo "PASS ${engine}"
    else
        failed+=("$engine")
        echo "FAIL ${engine}"
    fi
done

echo "======== SMOKE SUMMARY ========"
echo "passed: ${passed[*]:-none}"
echo "failed: ${failed[*]:-none}"
if [[ ${#failed[@]} -gt 0 ]]; then
    exit 1
fi
