# Chroma Parameters

See https://cookbook.chromadb.dev/core/configuration/#hnsw-configuration

`hnsw:M` cannot be changed after index creation.
`hnsw:construction_ef` cannot be changed after index creation.
`hnsw:search_ef` can be changed.

Parallel > 1 for searching is currently not supported because Chroma is not process-safe (see https://github.com/qdrant/vector-db-benchmark/pull/205#discussion_r1781471419).

## collection_params
    "metadata": {
        "hnsw:M": 16,32,64,
        "hnsw:construction_ef": 128,256,512
    }

## search_params
    "parallel": 1                      # implemented in base_client
    "top": /                           # implemented in base_client
    "metadata": {
        "hnsw:search_ef": 128,256,512
    }

## upload_params
non-default not in use.

    "parallel": 16                      # implemented in base_client
    "batch_size": 1024                  # implemented in base_client

