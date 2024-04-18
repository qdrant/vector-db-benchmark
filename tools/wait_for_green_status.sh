#!/bin/bash
# This scripts helps to wait for Opensearch|Elasticsearch status to become Green

set -e

SEARCH_CLUSTER_HOST=${1:-"localhost:9200"}

# Wait until the search cluster host is available
until $(curl --output /dev/null --silent --head --fail "$SEARCH_CLUSTER_HOST"); do
    printf '.'
    sleep 1 # Wait for 1 second
done

# Wait for ES/OS to start
response=$(curl --write-out %{http_code} --silent --output /dev/null "$SEARCH_CLUSTER_HOST")

until [ "$response" = "200" ]; do
    response=$(curl --write-out %{http_code} --silent --output /dev/null "$SEARCH_CLUSTER_HOST")
    >&2 echo "Search cluster is unavailable - sleep 1s"
    sleep 1
done

# Wait for ES/OS status to turn Green
health="$(curl -fsSL "$SEARCH_CLUSTER_HOST/_cat/health?h=status")"
health="$(echo "$health" | sed -r 's/^[[:space:]]+|[[:space:]]+$//g')"

until [ "$health" = 'green' ]; do
    health="$(curl -fsSL "$SEARCH_CLUSTER_HOST/_cat/health?h=status")"
    health="$(echo "$health" | sed -r 's/^[[:space:]]+|[[:space:]]+$//g')"
    >&2 echo "Search cluster status is not green yet - sleep 1s"
    sleep 1
done

>&2 echo "Search cluster is up"