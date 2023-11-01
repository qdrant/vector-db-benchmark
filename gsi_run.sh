#!/bin/bash

# python3 run.py --engines gsi-64-flat --datasets glove-25-angular
# python3 run.py --engines gsi-128-flat --datasets glove-25-angular
# python3 run.py --engines gsi-256-flat --datasets glove-25-angular
# python3 run.py --engines gsi-512-flat --datasets glove-25-angular
# python3 run.py --engines gsi-768-flat --datasets glove-25-angular

# python3 run.py --engines gsi-64-flat --datasets glove-100-angular
# python3 run.py --engines gsi-128-flat --datasets glove-100-angular
# python3 run.py --engines gsi-256-flat --datasets glove-100-angular
# python3 run.py --engines gsi-512-flat --datasets glove-100-angular
# python3 run.py --engines gsi-768-flat --datasets glove-100-angular

# python3 run.py --engines gsi-64-hnsw --datasets glove-25-angular
# python3 run.py --engines gsi-128-hnsw --datasets glove-25-angular
# python3 run.py --engines gsi-256-hnsw --datasets glove-25-angular
# python3 run.py --engines gsi-512-hnsw --datasets glove-25-angular
# python3 run.py --engines gsi-768-hnsw --datasets glove-25-angular

# python3 run.py --engines gsi-64-hnsw --datasets glove-100-angular
# python3 run.py --engines gsi-128-hnsw --datasets glove-100-angular
# python3 run.py --engines gsi-256-hnsw --datasets glove-100-angular
# python3 run.py --engines gsi-512-hnsw --datasets glove-100-angular
# python3 run.py --engines gsi-768-hnsw --datasets glove-100-angular

# python3 run.py --engines gsi-64-flat --datasets deep-image-96-angular
# python3 run.py --engines gsi-128-flat --datasets deep-image-96-angular
# python3 run.py --engines gsi-256-flat --datasets deep-image-96-angular
# python3 run.py --engines gsi-512-flat --datasets deep-image-96-angular
# python3 run.py --engines gsi-768-flat --datasets deep-image-96-angular

# python3 run.py --engines gsi-64-hnsw --datasets deep-image-96-angular
# python3 run.py --engines gsi-128-hnsw --datasets deep-image-96-angular
# python3 run.py --engines gsi-256-hnsw --datasets deep-image-96-angular
# python3 run.py --engines gsi-512-hnsw --datasets deep-image-96-angular
# python3 run.py --engines gsi-768-hnsw --datasets deep-image-96-angular

# python3 run.py --engines gsi-128-hnsw-m-64-ef-128 --datasets glove*
# python3 run.py --engines gsi-256-hnsw-m-64-ef-128 --datasets glove*
# python3 run.py --engines gsi-512-hnsw-m-64-ef-128 --datasets glove*
# python3 run.py --engines gsi-768-hnsw-m-64-ef-128 --datasets glove*

# python3 run.py --engines gsi-128-hnsw-m-64-ef-128 --datasets deep-image-96-angular
# python3 run.py --engines gsi-256-hnsw-m-64-ef-128 --datasets deep-image-96-angular
# python3 run.py --engines gsi-512-hnsw-m-64-ef-128 --datasets deep-image-96-angular
# python3 run.py --engines gsi-768-hnsw-m-64-ef-128 --datasets deep-image-96-angular

# python3 run.py --engines gsi-128-hnsw-m-64-ef-256 --datasets deep-image-96-angular
# python3 run.py --engines gsi-256-hnsw-m-64-ef-256 --datasets deep-image-96-angular
# python3 run.py --engines gsi-512-hnsw-m-64-ef-256 --datasets deep-image-96-angular
# python3 run.py --engines gsi-768-hnsw-m-64-ef-256 --datasets deep-image-96-angular

# python3 run.py --engines gsi-128-hnsw-m-64-ef-512 --datasets deep-image-96-angular
# python3 run.py --engines gsi-256-hnsw-m-64-ef-512 --datasets deep-image-96-angular
# python3 run.py --engines gsi-512-hnsw-m-64-ef-512 --datasets deep-image-96-angular
# python3 run.py --engines gsi-768-hnsw-m-64-ef-512 --datasets deep-image-96-angular

# python3 run.py --engines qdrant-m-64-ef-512 --datasets laion-small-clip
# python3 run.py --engines qdrant-m-64-ef-512 --datasets gist-960-angular

# python3 run.py --engines weaviate-m-64-ef-512 --datasets laion-small-clip
# python3 run.py --engines weaviate-m-64-ef-512 --datasets gist-960-angular

# export dataset="laion-small-clip"
# python3 run.py --engines gsi-128-clusters --datasets laion-small-clip
# python3 run.py --engines gsi-256-clusters --datasets laion-small-clip
# python3 run.py --engines gsi-512-clusters --datasets laion-small-clip
# python3 run.py --engines gsi-768-clusters --datasets laion-small-clip
export dataset="gist-960-angular"
python3 run.py --engines gsi-128-clusters --datasets gist-960-angular
python3 run.py --engines gsi-256-clusters --datasets gist-960-angular
python3 run.py --engines gsi-512-clusters --datasets gist-960-angular
python3 run.py --engines gsi-768-clusters --datasets gist-960-angular
