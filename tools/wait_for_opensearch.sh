#!/bin/bash

set -e

ES_HOST=${1:-"localhost:9200"}

until $(curl --output /dev/null --silent --head --fail "$ES_HOST"); do
    printf '.'
    sleep 1
done

>&2 echo "Open Search is up"