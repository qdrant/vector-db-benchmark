#!/usr/bin/env bash

set -e


# write docker stats into file each second
function write_stats {
  while true; do
    docker stats --no-stream --format "{{ json . }}" >> $1
    sleep 10
  done
}


# Ensure that only one instance of this script is running at a time
(
  flock -n 200
  write_stats docker.stats.jsonl
) 200>monitor.lock
