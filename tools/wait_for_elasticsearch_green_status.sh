#!/bin/bash

set -e

ES_HOST=${1:-"localhost:9200"}

until $(curl --output /dev/null --silent --head --fail "$ES_HOST"); do
    printf '.'
    sleep 1
done

# Wait for ES to start...
response=$(curl "$ES_HOST")
until [ "$response" = "200" ]; do
    response=$(curl --write-out %{http_code} --silent --output /dev/null "$ES_HOST")
    >&2 echo "Elastic Search is unavailable - sleeping"
    sleep 1
done

# Wait for ES status to turn to Green
health="$(curl -fsSL "$ES_HOST/_cat/health?h=status")"
health="$(echo "$health" | sed -r 's/^[[:space:]]+|[[:space:]]+$//g')"

until [ "$health" = 'green' ]; do
    health="$(curl -fsSL "$ES_HOST/_cat/health?h=status")"
    health="$(echo "$health" | sed -r 's/^[[:space:]]+|[[:space:]]+$//g')"
    >&2 echo "Elastic Search is yet unavailable, sleep 1"
    sleep 1
done

>&2 echo "Elastic Search is up"