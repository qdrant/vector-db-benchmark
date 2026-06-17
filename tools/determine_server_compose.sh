#!/bin/bash

set -e

# Script to determine the appropriate server compose file based on engine configuration
# This script maps engine configurations to their corresponding server compose files

ENGINE_NAME=${1:-"qdrant-continuous-benchmark"}

# Function to get engine type from engine name
get_engine_type() {
    local engine_name="$1"
    
    # Extract engine type from the engine name
    # Most engines follow the pattern: {engine_type}-{config}
    # e.g., qdrant-continuous-benchmark -> qdrant
    #      elasticsearch-default -> elasticsearch
    #      milvus-default -> milvus
    
    if [[ "$engine_name" == qdrant-* ]]; then
        echo "qdrant"
    elif [[ "$engine_name" == elasticsearch-* ]]; then
        echo "elasticsearch"
    elif [[ "$engine_name" == opensearch-* ]]; then
        echo "opensearch"
    elif [[ "$engine_name" == milvus-* ]]; then
        echo "milvus"
    elif [[ "$engine_name" == weaviate-* ]]; then
        echo "weaviate"
    elif [[ "$engine_name" == redis-* ]]; then
        echo "redis"
    elif [[ "$engine_name" == pgvector-* ]]; then
        echo "pgvector"
    else
        echo "unknown"
    fi
}

# Function to determine server compose file based on engine type
get_server_compose_file() {
    local engine_type="$1"
    local engine_name="$2"
    
    case "$engine_type" in
        "qdrant")
            # For Qdrant, we can use different compose files based on the configuration
            if [[ "$engine_name" == *"continuous"* ]]; then
                echo "qdrant-continuous-benchmarks"
            elif [[ "$engine_name" == *"cluster"* ]]; then
                echo "qdrant-cluster-mode"
            elif [[ "$engine_name" == *"billion"* ]]; then
                echo "qdrant-billion-scale"
            elif [[ "$engine_name" == *"limit"* ]]; then
                echo "qdrant-limit-ram"
            else
                echo "qdrant-single-node"
            fi
            ;;
        "elasticsearch")
            echo "elasticsearch-single-node"
            ;;
        "opensearch")
            echo "opensearch-single-node"
            ;;
        "milvus")
            if [[ "$engine_name" == *"limit"* ]]; then
                echo "milvus-limit-ram"
            else
                echo "milvus-single-node"
            fi
            ;;
        "weaviate")
            echo "weaviate-single-node"
            ;;
        "redis")
            echo "redis-single-node"
            ;;
        "pgvector")
            echo "pgvector-single-node"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Main logic
ENGINE_TYPE=$(get_engine_type "$ENGINE_NAME")
SERVER_COMPOSE=$(get_server_compose_file "$ENGINE_TYPE" "$ENGINE_NAME")

if [[ "$SERVER_COMPOSE" == "unknown" ]]; then
    echo "Error: Unknown engine type '$ENGINE_TYPE' for engine '$ENGINE_NAME'" >&2
    echo "Available engine types: qdrant, elasticsearch, opensearch, milvus, weaviate, redis, pgvector" >&2
    exit 1
fi

echo "$SERVER_COMPOSE"
