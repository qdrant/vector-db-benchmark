#!/bin/bash

set -e
set -x

VECTOR_DB=${VECTOR_DB:-qdrant}
BRANCH=${BRANCH:-master}

if [ -d "./vector-db-benchmark" ]; then
    echo "vector-db-benchmark repo already exists"
else
    git clone https://github.com/qdrant/vector-db-benchmark
fi

cd vector-db-benchmark
git fetch && git checkout $BRANCH && git pull

python3 -m poetry install

# if using qdrant vector db
if [ "$VECTOR_DB" == "qdrant" ]; then
    QDRANT_CONFIGS=$(cat experiments/configurations/qdrant-single-node{-bq-rps,-sq-rps,-rps,}.json | jq '.[] | .name' | grep -E 'qdrant(-(rps|bq-rps|sq-rps))?-m-.*-ef-.*' | sed 's/"//g')

    for QDRANT_CONFIG in $QDRANT_CONFIGS; do
        # upload
        python3 -m poetry run python run.py --engines "${QDRANT_CONFIG}" --datasets $DATASET --host $PRIVATE_SERVER_IP --skip-search >> ${VECTOR_DB}.log 2>&1

        # now run search (retry on errors)
        set +e
        while true; do
            python3 -m poetry run python run.py --engines "${QDRANT_CONFIG}" --datasets $DATASET --host $PRIVATE_SERVER_IP >> ${VECTOR_DB}.log --skip-upload 2>&1
            if [ $? -ne 0 ]; then
                echo "retrying" | tee -a ${VECTOR_DB}.log
                sleep 1
            else
                echo "done" | tee -a ${VECTOR_DB}.log
                break
            fi
        done
        set -e
    done
else
    nohup python3 -m poetry run python run.py --engines "${VECTOR_DB}-m-*-ef-*" --datasets $DATASET --host $PRIVATE_SERVER_IP >> ${VECTOR_DB}.log 2>&1 &
fi

PID_BENCHMARK=$!
echo $PID_BENCHMARK > benchmark.pid
wait $PID_BENCHMARK
