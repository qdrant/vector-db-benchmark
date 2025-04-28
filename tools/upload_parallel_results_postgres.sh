#!/bin/bash


# Read search results from json file and upload it to postgres
#
# Assume table:
# create table benchmark_parallel_search_upload (
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
# 	search_time real,
# 	no_upsert_search_time real,
# 	cpu real,
# 	cpu_telemetry real,
# );

PARALLEL_SEARCH_RESULTS_FILE=${PARALLEL_SEARCH_RESULTS_FILE:-""}
SEARCH_RESULT_FILE=${SEARCH_RESULTS_FILE:-""}
PARALLEL_UPLOAD_RESULTS_FILE=${PARALLEL_UPLOAD_RESULTS_FILE:-""}
UPLOAD_RESULTS_FILE=${UPLOAD_RESULTS_FILE:-""}
ROOT_API_RESPONSE_FILE=${ROOT_API_RESPONSE_FILE:-""}
POSTGRES_TABLE=${POSTGRES_TABLE:-"benchmark_parallel_search_upload"}

QDRANT_VERSION=${QDRANT_VERSION:-"dev"}
DATASETS=${DATASETS:-"laion-small-clip"}

IS_CI_RUN=${IS_CI_RUN:-"false"}

if [[ "$BENCHMARK_STRATEGY" != "parallel" ]]; then
  echo "BENCHMARK_STRATEGY is not parallel"
  exit 1
else
  if [[ -z "$PARALLEL_SEARCH_RESULTS_FILE" ]]; then
    echo "PARALLEL_SEARCH_RESULTS_FILE is not set"
    exit 1
  fi

  if [[ -z "$SEARCH_RESULT_FILE" ]]; then
    echo "SEARCH_RESULT_FILE is not set"
    exit 1
  fi

  if [[ -z "$PARALLEL_UPLOAD_RESULTS_FILE" ]]; then
    echo "PARALLEL_UPLOAD_RESULTS_FILE is not set"
    exit 1
  fi

  if [[ -z "$UPLOAD_RESULTS_FILE" ]]; then
    echo "UPLOAD_RESULTS_FILE is not set"
    exit 1
  fi
fi

if [[ -z "$ROOT_API_RESPONSE_FILE" ]]; then
  echo "ROOT_API_RESPONSE_FILE is not set"
  exit 1
fi

if [[ "$BENCHMARK_STRATEGY" == "default" ]]; then
  if [[ -z "$CPU_USAGE_FILE" ]]; then
    echo "CPU_USAGE_FILE is not set"
    exit 1
  fi
fi

RPS=NULL
MEAN_PRECISIONS=NULL
P95_TIME=NULL
P99_TIME=NULL
UPLOAD_TIME=NULL
INDEXING_TIME=NULL
SEARCH_TIME=NULL
NO_UPSERT_SEARCH_TIME=NULL
CPU=NULL
CPU_TELEMETRY=NULL

RPS=$(jq -r '.results.rps' "$PARALLEL_SEARCH_RESULTS_FILE")
MEAN_PRECISIONS=$(jq -r '.results.mean_precisions' "$PARALLEL_SEARCH_RESULTS_FILE")
P95_TIME=$(jq -r '.results.p95_time' "$PARALLEL_SEARCH_RESULTS_FILE")
P99_TIME=$(jq -r '.results.p99_time' "$PARALLEL_SEARCH_RESULTS_FILE")
SEARCH_TIME=$(jq -r '.results.total_time' "$PARALLEL_SEARCH_RESULTS_FILE")
NO_UPSERT_SEARCH_TIME=$(jq -r '.results.total_time' "$SEARCH_RESULT_FILE")

UPLOAD_TIME=$(jq -r '.results.upload_time' "$PARALLEL_UPLOAD_RESULTS_FILE")
INDEXING_TIME=$(jq -r '.results.total_time' "$PARALLEL_UPLOAD_RESULTS_FILE")

if [[ "$BENCHMARK_STRATEGY" == "default" ]]; then
  # Only this strategy produces cpu usage results files
  CPU=$(cat "$CPU_USAGE_FILE" | tr -d '[:space:]')
fi
CPU_TELEMETRY=$(jq -r '.result.hardware.collection_data.benchmark.cpu' "$TELEMETRY_API_RESPONSE_FILE")

QDRANT_COMMIT=$(jq -r '.commit' "$ROOT_API_RESPONSE_FILE")

MEASURE_TIMESTAMP=${MEASURE_TIMESTAMP:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}


docker run --name "vector-db" --rm jbergknoff/postgresql-client "postgresql://qdrant:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/postgres" -c "
INSERT INTO ${POSTGRES_TABLE} (engine, branch, commit, dataset, measure_timestamp, upload_time, indexing_time, rps, mean_precisions, p95_time, p99_time, search_time, no_upsert_search_time, cpu_telemetry, cpu)
VALUES ('qdrant-ci', '${QDRANT_VERSION}', '${QDRANT_COMMIT}', '${DATASETS}', '${MEASURE_TIMESTAMP}', ${UPLOAD_TIME}, ${INDEXING_TIME}, ${RPS}, ${MEAN_PRECISIONS}, ${P95_TIME}, ${P99_TIME}, ${SEARCH_TIME}, ${NO_UPSERT_SEARCH_TIME}, ${CPU_TELEMETRY}, ${CPU});
"

if [[ "$IS_CI_RUN" == "true" ]]; then
  echo "rps=${RPS}" >> "$GITHUB_OUTPUT"
  echo "mean_precisions=${MEAN_PRECISIONS}" >> "$GITHUB_OUTPUT"
  echo "p95_time=${P95_TIME}" >> "$GITHUB_OUTPUT"
  echo "p99_time=${P99_TIME}" >> "$GITHUB_OUTPUT"

  echo "search_time=${SEARCH_TIME}" >> "$GITHUB_OUTPUT"
  echo "no_upsert_search_time=${NO_UPSERT_SEARCH_TIME}" >> "$GITHUB_OUTPUT"

  echo "upload_time=${UPLOAD_TIME}" >> "$GITHUB_OUTPUT"
  echo "indexing_time=${INDEXING_TIME}" >> "$GITHUB_OUTPUT"

  echo "cpu_telemetry=${CPU_TELEMETRY}" >> "$GITHUB_OUTPUT"
  echo "cpu=${CPU}" >> "$GITHUB_OUTPUT"
fi
