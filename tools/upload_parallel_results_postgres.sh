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
#   no_upsert_search_time real,
# );

SEARCH_RESULTS_FILE=${SEARCH_RESULTS_FILE:-""}
NO_UPSERT_SEARCH_RESULT_FILE=${NO_UPSERT_SEARCH_RESULT_FILE:-""}
UPLOAD_RESULTS_FILE=${UPLOAD_RESULTS_FILE:-""}
ROOT_API_RESPONSE_FILE=${ROOT_API_RESPONSE_FILE:-""}
POSTGRES_TABLE=${POSTGRES_TABLE:-"benchmark_parallel_search_upload"}

QDRANT_VERSION=${QDRANT_VERSION:-"dev"}
DATASETS=${DATASETS:-"laion-small-clip"}

if [[ "$BENCHMARK_STRATEGY" != "parallel" ]]; then
  echo "BENCHMARK_STRATEGY is not parallel"
  exit 1
else
  if [[ -z "$SEARCH_RESULTS_FILE" ]]; then
    echo "SEARCH_RESULTS_FILE is not set"
    exit 1
  fi

  if [[ -z "$NO_UPSERT_SEARCH_RESULT_FILE" ]]; then
    echo "NO_UPSERT_SEARCH_RESULT_FILE is not set"
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

RPS=NULL
MEAN_PRECISIONS=NULL
P95_TIME=NULL
P99_TIME=NULL
UPLOAD_TIME=NULL
INDEXING_TIME=NULL
SEARCH_TIME=NULL

RPS=$(jq -r '.results.rps' "$SEARCH_RESULTS_FILE")
MEAN_PRECISIONS=$(jq -r '.results.mean_precisions' "$SEARCH_RESULTS_FILE")
P95_TIME=$(jq -r '.results.p95_time' "$SEARCH_RESULTS_FILE")
P99_TIME=$(jq -r '.results.p99_time' "$SEARCH_RESULTS_FILE")
SEARCH_TIME=$(jq -r '.results.total_time' "$SEARCH_RESULTS_FILE")
NO_UPSERT_SEARCH_TIME=$(jq -r '.results.total_time' "$NO_UPSERT_SEARCH_RESULT_FILE")

UPLOAD_TIME=$(jq -r '.results.upload_time' "$UPLOAD_RESULTS_FILE")
INDEXING_TIME=$(jq -r '.results.total_time' "$UPLOAD_RESULTS_FILE")

QDRANT_COMMIT=$(jq -r '.commit' "$ROOT_API_RESPONSE_FILE")

MEASURE_TIMESTAMP=${MEASURE_TIMESTAMP:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}


docker run --name "vector-db" --rm jbergknoff/postgresql-client "postgresql://qdrant:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/postgres" -c "
INSERT INTO ${POSTGRES_TABLE} (engine, branch, commit, dataset, measure_timestamp, upload_time, indexing_time, rps, mean_precisions, p95_time, p99_time, search_time, no_upsert_search_time)
VALUES ('qdrant-ci', '${QDRANT_VERSION}', '${QDRANT_COMMIT}', '${DATASETS}', '${MEASURE_TIMESTAMP}', ${UPLOAD_TIME}, ${INDEXING_TIME}, ${RPS}, ${MEAN_PRECISIONS}, ${P95_TIME}, ${P99_TIME}, ${SEARCH_TIME}, ${NO_UPSERT_SEARCH_TIME});
"

