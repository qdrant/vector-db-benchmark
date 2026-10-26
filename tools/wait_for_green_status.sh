#!/bin/bash
# This scripts helps to wait for Opensearch|Elasticsearch status to become Green

set -e

SEARCH_CLUSTER_HOST=${1:-"localhost:9200"}
TIMEOUT=${2:-180}
elapsed=0
tick() {
    elapsed=$((elapsed + 1))
    if [ "$elapsed" -ge "$TIMEOUT" ]; then
        echo "timed out waiting for search cluster at $SEARCH_CLUSTER_HOST" >&2
        exit 1
    fi
}

# Wait until the search cluster host is available
until $(curl --output /dev/null --silent --head --fail "http://$SEARCH_CLUSTER_HOST"); do
    printf '.'
    sleep 1
    tick
done

# Wait for ES/OS to start
response=$(curl --write-out %{http_code} --silent --output /dev/null "http://$SEARCH_CLUSTER_HOST")

until [ "$response" = "200" ]; do
    response=$(curl --write-out %{http_code} --silent --output /dev/null "http://$SEARCH_CLUSTER_HOST")
    >&2 echo "Search cluster is unavailable - sleep 1s"
    sleep 1
    tick
done

# Wait for ES/OS status to turn Green
health="$(curl -fsSL "http://$SEARCH_CLUSTER_HOST/_cat/health?h=status")"
health="$(echo "$health" | sed -r 's/^[[:space:]]+|[[:space:]]+$//g')"

until [ "$health" = 'green' ] || [ "$health" = 'yellow' ]; do
    health="$(curl -fsSL "http://$SEARCH_CLUSTER_HOST/_cat/health?h=status")"
    health="$(echo "$health" | sed -r 's/^[[:space:]]+|[[:space:]]+$//g')"
    >&2 echo "Search cluster status is ${health:-unknown} - sleep 1s"
    sleep 1
    tick
done

>&2 echo "Search cluster is up"