#!/usr/bin/env bash


rsync -avP \
  $1:./projects/vector-db-benchmark/results/ \
  ./results/