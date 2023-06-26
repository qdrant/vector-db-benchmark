#!/bin/bash

set -e


# Install dependencies on the server for running client
cd "$HOME/projects/vector-db-benchmark/"

pip install poetry
poetry install

