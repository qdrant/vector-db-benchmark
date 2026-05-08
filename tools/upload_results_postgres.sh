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
# 	rss_anon_mem real,
# 	collection_load_time_ms real,
# 	cpu real,
# 	cpu_telemetry real,
# 	storage_size_bytes bigint,
# 	storage_size_apparent_bytes bigint,
# );

SEARCH_RESULTS_FILE=${SEARCH_RESULTS_FILE:-""}
UPLOAD_RESULTS_FILE=${UPLOAD_RESULTS_FILE:-""}
VM_RSS_MEMORY_USAGE_FILE=${VM_RSS_MEMORY_USAGE_FILE:-""}
RSS_ANON_MEMORY_USAGE_FILE=${RSS_ANON_MEMORY_USAGE_FILE:-""}
ROOT_API_RESPONSE_FILE=${ROOT_API_RESPONSE_FILE:-""}
TELEMETRY_API_RESPONSE_FILE=${TELEMETRY_API_RESPONSE_FILE:-""}
STORAGE_SIZE_ALLOCATED_FILE=${STORAGE_SIZE_ALLOCATED_FILE:-""}
STORAGE_SIZE_APPARENT_FILE=${STORAGE_SIZE_APPARENT_FILE:-""}
METRICS_BEFORE_FILE=${METRICS_BEFORE_FILE:-""}
METRICS_AFTER_FILE=${METRICS_AFTER_FILE:-""}
MEMORY_BEFORE_FILE=${MEMORY_BEFORE_FILE:-""}
MEMORY_AFTER_FILE=${MEMORY_AFTER_FILE:-""}
CGROUP_BEFORE_FILE=${CGROUP_BEFORE_FILE:-""}
CGROUP_AFTER_FILE=${CGROUP_AFTER_FILE:-""}
POSTGRES_TABLE=${POSTGRES_TABLE:-"benchmark"}

QDRANT_VERSION=${QDRANT_VERSION:-"dev"}
DATASETS=${DATASETS:-"laion-small-clip"}

IS_CI_RUN=${IS_CI_RUN:-"false"}

if [[ "$BENCHMARK_STRATEGY" == "collection-reload" ]]; then
  if [[ -z "$TELEMETRY_API_RESPONSE_FILE" ]]; then
    echo "TELEMETRY_API_RESPONSE_FILE is not set"
    exit 1
  fi
elif [[ "$BENCHMARK_STRATEGY" == "search-on-disk" || "$BENCHMARK_STRATEGY" == "search-on-disk-search" ]]; then
  # snapshot-restore, no upload phase → only search results expected
  if [[ -z "$SEARCH_RESULTS_FILE" ]]; then
    echo "SEARCH_RESULTS_FILE is not set"
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

if [[ "$BENCHMARK_STRATEGY" == "default" ]]; then
  if [[ -z "$CPU_USAGE_FILE" ]]; then
    echo "CPU_USAGE_FILE is not set"
    exit 1
  fi
fi

COLLECTION_LOAD_TIME=NULL
RPS=NULL
MEAN_PRECISIONS=NULL
P95_TIME=NULL
P99_TIME=NULL
UPLOAD_TIME=NULL
INDEXING_TIME=NULL
CPU=NULL
CPU_TELEMETRY=NULL
STORAGE_SIZE_ALLOCATED=NULL
STORAGE_SIZE_APPARENT=NULL
MINOR_PAGE_FAULTS=NULL
MAJOR_PAGE_FAULTS=NULL
MEM_DISK_BYTES=NULL
MEM_EXPECTED_CACHE_BYTES=NULL
MEM_CACHED_BYTES_BEFORE=NULL
MEM_CACHED_BYTES_AFTER=NULL
CGROUP_MEM_CURRENT_BEFORE=NULL
CGROUP_MEM_CURRENT_AFTER=NULL

if [[ "$BENCHMARK_STRATEGY" == "collection-reload" ]]; then
  # this strategy does not produce search & upload results files
  echo "BENCHMARK_STRATEGY is $BENCHMARK_STRATEGY, upload telemetry"
  COLLECTION_LOAD_TIME=$(jq -r '.result.collections.collections[] | select(.id == "benchmark") | .init_time_ms' "$TELEMETRY_API_RESPONSE_FILE")
elif [[ "$BENCHMARK_STRATEGY" == "search-on-disk" || "$BENCHMARK_STRATEGY" == "search-on-disk-search" ]]; then
  # search-only — snapshot supplies the data, no upload metrics
  RPS=$(jq -r '.results.rps' "$SEARCH_RESULTS_FILE")
  MEAN_PRECISIONS=$(jq -r '.results.mean_precisions' "$SEARCH_RESULTS_FILE")
  P95_TIME=$(jq -r '.results.p95_time' "$SEARCH_RESULTS_FILE")
  P99_TIME=$(jq -r '.results.p99_time' "$SEARCH_RESULTS_FILE")
else
  # any other strategies are considered to have search & upload results
  RPS=$(jq -r '.results.rps' "$SEARCH_RESULTS_FILE")
  MEAN_PRECISIONS=$(jq -r '.results.mean_precisions' "$SEARCH_RESULTS_FILE")
  P95_TIME=$(jq -r '.results.p95_time' "$SEARCH_RESULTS_FILE")
  P99_TIME=$(jq -r '.results.p99_time' "$SEARCH_RESULTS_FILE")

  UPLOAD_TIME=$(jq -r '.results.upload_time' "$UPLOAD_RESULTS_FILE")
  INDEXING_TIME=$(jq -r '.results.total_time' "$UPLOAD_RESULTS_FILE")
fi

VM_RSS_MEMORY_USAGE=$(cat "$VM_RSS_MEMORY_USAGE_FILE" | tr -d '[:space:]')
RSS_ANON_MEMORY_USAGE=$(cat "$RSS_ANON_MEMORY_USAGE_FILE" | tr -d '[:space:]')

if [[ "$BENCHMARK_STRATEGY" == "default" ]]; then
  # Only this strategy produces cpu usage results files
  CPU=$(cat "$CPU_USAGE_FILE" | tr -d '[:space:]')
fi
CPU_TELEMETRY=$(jq -r '.result.hardware.collection_data.benchmark.cpu' "$TELEMETRY_API_RESPONSE_FILE")

if [[ -n "$STORAGE_SIZE_ALLOCATED_FILE" && -f "$STORAGE_SIZE_ALLOCATED_FILE" ]]; then
  STORAGE_SIZE_ALLOCATED=$(cat "$STORAGE_SIZE_ALLOCATED_FILE" | tr -d '[:space:]')
  STORAGE_SIZE_ALLOCATED=${STORAGE_SIZE_ALLOCATED:-NULL}
fi
if [[ -n "$STORAGE_SIZE_APPARENT_FILE" && -f "$STORAGE_SIZE_APPARENT_FILE" ]]; then
  STORAGE_SIZE_APPARENT=$(cat "$STORAGE_SIZE_APPARENT_FILE" | tr -d '[:space:]')
  STORAGE_SIZE_APPARENT=${STORAGE_SIZE_APPARENT:-NULL}
fi

# Page-fault deltas across the search phase (search-on-disk strategy).
if [[ -n "$METRICS_BEFORE_FILE" && -f "$METRICS_BEFORE_FILE" && \
      -n "$METRICS_AFTER_FILE"  && -f "$METRICS_AFTER_FILE" ]]; then
  parse_metric() {
    grep -E "^${2} " "$1" | awk '{print $2}' | tr -d '[:space:]'
  }
  MINOR_BEFORE=$(parse_metric "$METRICS_BEFORE_FILE" "process_minor_page_faults_total")
  MAJOR_BEFORE=$(parse_metric "$METRICS_BEFORE_FILE" "process_major_page_faults_total")
  MINOR_AFTER=$(parse_metric "$METRICS_AFTER_FILE"  "process_minor_page_faults_total")
  MAJOR_AFTER=$(parse_metric "$METRICS_AFTER_FILE"  "process_major_page_faults_total")
  if [[ -n "$MINOR_BEFORE" && -n "$MINOR_AFTER" ]]; then
    MINOR_PAGE_FAULTS=$((MINOR_AFTER - MINOR_BEFORE))
  fi
  if [[ -n "$MAJOR_BEFORE" && -n "$MAJOR_AFTER" ]]; then
    MAJOR_PAGE_FAULTS=$((MAJOR_AFTER - MAJOR_BEFORE))
  fi
fi

# Per-collection memory report from Qdrant (search-on-disk strategy).
# cached_bytes_after / disk_bytes is the proof signal for whether the
# working set actually lives on disk (low ratio) vs RAM-resident (~1.0).
if [[ -n "$MEMORY_BEFORE_FILE" && -f "$MEMORY_BEFORE_FILE" && \
      -n "$MEMORY_AFTER_FILE"  && -f "$MEMORY_AFTER_FILE" ]]; then
  parse_mem() {
    # $1 = file, $2 = dotted path under .result.total (e.g. cached_bytes)
    jq -r ".result.total.$2 // empty" "$1" | tr -d '[:space:]'
  }
  MEM_DISK_BYTES=$(parse_mem               "$MEMORY_AFTER_FILE"  "disk_bytes")
  MEM_EXPECTED_CACHE_BYTES=$(parse_mem     "$MEMORY_AFTER_FILE"  "expected_cache_bytes")
  MEM_CACHED_BYTES_BEFORE=$(parse_mem      "$MEMORY_BEFORE_FILE" "cached_bytes")
  MEM_CACHED_BYTES_AFTER=$(parse_mem       "$MEMORY_AFTER_FILE"  "cached_bytes")
  : "${MEM_DISK_BYTES:=NULL}"
  : "${MEM_EXPECTED_CACHE_BYTES:=NULL}"
  : "${MEM_CACHED_BYTES_BEFORE:=NULL}"
  : "${MEM_CACHED_BYTES_AFTER:=NULL}"
fi

parse_cgroup() {
  [[ -n "$1" && -f "$1" ]] || { echo NULL; return; }
  local v
  v=$(cat "$1" | tr -d '[:space:]')
  echo "${v:-NULL}"
}
CGROUP_MEM_CURRENT_BEFORE=$(parse_cgroup "$CGROUP_BEFORE_FILE")
CGROUP_MEM_CURRENT_AFTER=$(parse_cgroup  "$CGROUP_AFTER_FILE")

QDRANT_COMMIT=$(jq -r '.commit' "$ROOT_API_RESPONSE_FILE")

MEASURE_TIMESTAMP=${MEASURE_TIMESTAMP:-$(date -u +"%Y-%m-%dT%H:%M:%SZ")}

# search-on-disk: encode the inline_storage variant in the dataset column so the two
# engine configs (inline-on / inline-off) produce distinct rows. The `engine` column
# stays 'qdrant-ci' for backward compatibility with existing dashboards.
DATASET_LABEL="$DATASETS"
if [[ "$BENCHMARK_STRATEGY" == "search-on-disk" || "$BENCHMARK_STRATEGY" == "search-on-disk-search" ]]; then
  case "${ENGINE_NAME:-}" in
    *-inline-on)  DATASET_LABEL="${DATASETS}@inline-on"  ;;
    *-inline-off) DATASET_LABEL="${DATASETS}@inline-off" ;;
  esac
fi

docker run --name "vector-db" --rm jbergknoff/postgresql-client "postgresql://qdrant:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/postgres" -c "
INSERT INTO ${POSTGRES_TABLE} (engine, branch, commit, dataset, measure_timestamp, upload_time, indexing_time, rps, mean_precisions, p95_time, p99_time, vm_rss_mem, rss_anon_mem, collection_load_time_ms, cpu_telemetry, cpu, storage_size_bytes, storage_size_apparent_bytes, minor_page_faults, major_page_faults, mem_disk_bytes, mem_expected_cache_bytes, mem_cached_bytes_before, mem_cached_bytes_after, cgroup_mem_current_before, cgroup_mem_current_after)
VALUES ('qdrant-ci', '${QDRANT_VERSION}', '${QDRANT_COMMIT}', '${DATASET_LABEL}', '${MEASURE_TIMESTAMP}', ${UPLOAD_TIME}, ${INDEXING_TIME}, ${RPS}, ${MEAN_PRECISIONS}, ${P95_TIME}, ${P99_TIME}, ${VM_RSS_MEMORY_USAGE}, ${RSS_ANON_MEMORY_USAGE}, ${COLLECTION_LOAD_TIME}, ${CPU_TELEMETRY}, ${CPU}, ${STORAGE_SIZE_ALLOCATED}, ${STORAGE_SIZE_APPARENT}, ${MINOR_PAGE_FAULTS}, ${MAJOR_PAGE_FAULTS}, ${MEM_DISK_BYTES}, ${MEM_EXPECTED_CACHE_BYTES}, ${MEM_CACHED_BYTES_BEFORE}, ${MEM_CACHED_BYTES_AFTER}, ${CGROUP_MEM_CURRENT_BEFORE}, ${CGROUP_MEM_CURRENT_AFTER});
"

if [[ "$IS_CI_RUN" == "true" ]]; then
  echo "collection_load_time=${COLLECTION_LOAD_TIME}" >> "$GITHUB_OUTPUT"

  echo "rps=${RPS}" >> "$GITHUB_OUTPUT"
  echo "mean_precisions=${MEAN_PRECISIONS}" >> "$GITHUB_OUTPUT"
  echo "p95_time=${P95_TIME}" >> "$GITHUB_OUTPUT"
  echo "p99_time=${P99_TIME}" >> "$GITHUB_OUTPUT"

  echo "vm_rss_memory_usage=${VM_RSS_MEMORY_USAGE}" >> "$GITHUB_OUTPUT"
  echo "rss_anon_memory_usage=${RSS_ANON_MEMORY_USAGE}" >> "$GITHUB_OUTPUT"

  echo "upload_time=${UPLOAD_TIME}" >> "$GITHUB_OUTPUT"
  echo "indexing_time=${INDEXING_TIME}" >> "$GITHUB_OUTPUT"

  echo "cpu_telemetry=${CPU_TELEMETRY}" >> "$GITHUB_OUTPUT"
  echo "cpu=${CPU}" >> "$GITHUB_OUTPUT"

  echo "storage_size_bytes=${STORAGE_SIZE_ALLOCATED}" >> "$GITHUB_OUTPUT"
  echo "storage_size_apparent_bytes=${STORAGE_SIZE_APPARENT}" >> "$GITHUB_OUTPUT"
fi
