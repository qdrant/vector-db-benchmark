#!/bin/bash



# file name pattern: qdrant-continuous-benchmark-laion-small-clip-upload-2023-08-01-23-09-25.json


# read dates from file names, without hours and minutes
ls -1 results/qdrant/qdrant-continuous-benchmark-laion-small-clip-upload-* | sed -e 's/.*upload-\(.*\)\.json/\1/' | sed -e 's/\(.*\)-\(.*\)-\(.*\)-\(.*\)-\(.*\)-\(.*\)/\1-\2-\3/' | sort | uniq > dates.txt


# read dates and search for files with the same date

while read -r date; do
  echo "Processing date: $date"
  SEARCH_FILE=$(ls -1 results/qdrant/*.json | grep "$date" | grep search | head -n 1)
  UPLOAD_FILE=$(ls -1 results/qdrant/*.json | grep "$date" | grep upload | head -n 1)

  echo "Search file: $SEARCH_FILE"
  echo "Upload file: $UPLOAD_FILE"

  SEARCH_RESULTS_FILE=$SEARCH_FILE \
    UPLOAD_RESULTS_FILE=$UPLOAD_FILE \
    MEMORY_USAGE_FILE=results/qdrant/mem-usage.txt \
    MEASURE_TIMESTAMP=$date \
    bash -x tools/upload_results_postgres.sh

done < dates.txt