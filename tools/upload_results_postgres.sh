#!/bin/bash


# Read search results from json file and upload it to postgres
#
# Assume table:
#create table benchmark (
#	id SERIAL PRIMARY key,
#	engine VARCHAR(255),
#	measure_timestamp TIMESTAMP,
#	upload_time real,
#	indexing_time real,
#	rps real,
#	mean_precisions real,
#	p95_time real,
#	p99_time real,
#	memory_usage real
#);

SEARCH_RESULTS_FILE=${SEARCH_RESULTS_FILE:-""}

if [[ -z "$SEARCH_RESULTS_FILE" ]]; then
  echo "SEARCH_RESULTS_FILE is not set"
  exit 1
fi

UPLOAD_RESULT_PATH=${UPLOAD_RESULT_PATH:-""}

if [[ -z "$UPLOAD_RESULTS_FILE" ]]; then
  echo "UPLOAD_RESULT_PATH is not set"
  exit 1
fi

MEMEORY_USAGE_FILE=${MEMEORY_USAGE_FILE:-""}

if [[ -z "$MEMEORY_USAGE_FILE" ]]; then
  echo "MEMEORY_USAGE_FILE is not set"
  exit 1
fi

RPS=$(jq -r '.results.rps' "$SEARCH_RESULTS_FILE")
MEAN_PRECISIONS=$(jq -r '.results.mean_precisions' "$SEARCH_RESULTS_FILE")
P95_TIME=$(jq -r '.results.p95_time' "$SEARCH_RESULTS_FILE")
P99_TIME=$(jq -r '.results.p99_time' "$SEARCH_RESULTS_FILE")

UPLOAD_TIME=$(jq -r '.results.upload_time' "$UPLOAD_RESULTS_FILE")
INDEXING_TIME=$(jq -r '.results.total_time' "$UPLOAD_RESULTS_FILE")

MEMORY_USAGE=$(cat "$MEMEORY_USAGE_FILE")

MEASURE_TIMESTAMP=${MEASURE_TIMESTAMP:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}


docker run -it --rm jbergknoff/postgresql-client "postgresql://qdrant:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/postgres" -c "
INSERT INTO benchmark (engine, measure_timestamp, upload_time, indexing_time, rps, mean_precisions, p95_time, p99_time, memory_usage)
VALUES (\"qdrant-ci\" '${MEASURE_TIMESTAMP}', ${UPLOAD_TIME}, ${INDEXING_TIME}, ${RPS}, ${MEAN_PRECISIONS}, ${P95_TIME}, ${P99_TIME}, ${MEMORY_USAGE});
"

