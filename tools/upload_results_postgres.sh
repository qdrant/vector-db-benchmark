#!/bin/bash


# Read search results from json file and upload it to postgres
#
# Assume table:
# create table benchmark (
# 	id SERIAL PRIMARY key,
# 	engine VARCHAR(255),
# 	branch VARCHAR(255),
# 	commit CHAR(40),
# 	dataset VARCHAR(255),
# 	measure_timestamp TIMESTAMP,
# 	upload_time real,
# 	indexing_time real,
# 	rps real,
# 	mean_precisions real,
# 	p95_time real,
# 	p99_time real,
# 	vm_rss_mem real,
# 	rss_anon_mem real
# 	collection_load_time_ms real
# );

SEARCH_RESULTS_FILE=${SEARCH_RESULTS_FILE:-""}
UPLOAD_RESULTS_FILE=${UPLOAD_RESULTS_FILE:-""}
VM_RSS_MEMORY_USAGE_FILE=${VM_RSS_MEMORY_USAGE_FILE:-""}
RSS_ANON_MEMORY_USAGE_FILE=${RSS_ANON_MEMORY_USAGE_FILE:-""}
ROOT_API_RESPONSE_FILE=${ROOT_API_RESPONSE_FILE:-""}
TELEMETRY_API_RESPONSE_FILE=${TELEMETRY_API_RESPONSE_FILE:-""}
POSTGRES_TABLE=${POSTGRES_TABLE:-"benchmark"}

QDRANT_VERSION=${QDRANT_VERSION:-"dev"}
DATASETS=${DATASETS:-"laion-small-clip"}

if [[ "$BENCHMARK_STRATEGY" == "collection-reload" ]]; then
  if [[ -z "$TELEMETRY_API_RESPONSE_FILE" ]]; then
    echo "TELEMETRY_API_RESPONSE_FILE is not set"
    exit 1
  fi
else
  # any other strategies are considered to have search & upload results
  if [[ -z "$SEARCH_RESULTS_FILE" ]]; then
    echo "SEARCH_RESULTS_FILE is not set"
    exit 1
  fi


  if [[ -z "$UPLOAD_RESULTS_FILE" ]]; then
    echo "UPLOAD_RESULTS_FILE is not set"
    exit 1
  fi
fi

if [[ -z "$VM_RSS_MEMORY_USAGE_FILE" ]]; then
  echo "VM_RSS_MEMORY_USAGE_FILE is not set"
  exit 1
fi

if [[ -z "$RSS_ANON_MEMORY_USAGE_FILE" ]]; then
  echo "RSS_ANON_MEMORY_USAGE_FILEis not set"
  exit 1
fi

if [[ -z "$ROOT_API_RESPONSE_FILE" ]]; then
  echo "ROOT_API_RESPONSE_FILE is not set"
  exit 1
fi

COLLECTION_LOAD_TIME=NULL
RPS=NULL
MEAN_PRECISIONS=NULL
P95_TIME=NULL
P99_TIME=NULL
UPLOAD_TIME=NULL
INDEXING_TIME=NULL

if [[ "$BENCHMARK_STRATEGY" == "collection-reload" ]]; then
  echo "BENCHMARK_STRATEGY is $BENCHMARK_STRATEGY, upload telemetry"
  COLLECTION_LOAD_TIME=$(jq -r '.result.collections.collections[] | select(.id == "benchmark") | .init_time_ms' "$TELEMETRY_API_RESPONSE_FILE")
else
  # any other strategies are considered to have search & upload results
  RPS=$(jq -r '.results.rps' "$SEARCH_RESULTS_FILE")
  MEAN_PRECISIONS=$(jq -r '.results.mean_precisions' "$SEARCH_RESULTS_FILE")
  P95_TIME=$(jq -r '.results.p95_time' "$SEARCH_RESULTS_FILE")
  P99_TIME=$(jq -r '.results.p99_time' "$SEARCH_RESULTS_FILE")

  UPLOAD_TIME=$(jq -r '.results.upload_time' "$UPLOAD_RESULTS_FILE")
  INDEXING_TIME=$(jq -r '.results.total_time' "$UPLOAD_RESULTS_FILE")
fi

VM_RSS_MEMORY_USAGE=$(cat "$VM_RSS_MEMORY_USAGE_FILE")
RSS_ANON_MEMORY_USAGE=$(cat "$RSS_ANON_MEMORY_USAGE_FILE")

QDRANT_COMMIT=$(jq -r '.commit' "$ROOT_API_RESPONSE_FILE")

MEASURE_TIMESTAMP=${MEASURE_TIMESTAMP:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}


docker run --name "vector-db" --rm jbergknoff/postgresql-client "postgresql://qdrant:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/postgres" -c "
INSERT INTO ${POSTGRES_TABLE} (engine, branch, commit, dataset, measure_timestamp, upload_time, indexing_time, rps, mean_precisions, p95_time, p99_time, vm_rss_mem, rss_anon_mem, collection_load_time_ms)
VALUES ('qdrant-ci', '${QDRANT_VERSION}', '${QDRANT_COMMIT}', '${DATASETS}', '${MEASURE_TIMESTAMP}', ${UPLOAD_TIME}, ${INDEXING_TIME}, ${RPS}, ${MEAN_PRECISIONS}, ${P95_TIME}, ${P99_TIME}, ${VM_RSS_MEMORY_USAGE}, ${RSS_ANON_MEMORY_USAGE}, ${COLLECTION_LOAD_TIME});
"

