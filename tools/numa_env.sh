#!/usr/bin/env bash
# Green-field SKU for a 2-socket host (this box is c6id.metal):
#   server  → NUMA node 0, physical cores only, local memory
#   client  → NUMA node 1, physical cores only, local memory
# SMT siblings stay unused so a search thread cannot share a core.
# Cross-node memory distance is 2×; pinning both CPU and memory removes that.

set -euo pipefail

NUMA_NODE_SERVER=${NUMA_NODE_SERVER:-0}
NUMA_NODE_CLIENT=${NUMA_NODE_CLIENT:-1}

_expand_cpulist() {
    local spec=$1
    local part start end i
    IFS=',' read -ra parts <<< "$spec"
    for part in "${parts[@]}"; do
        if [[ "$part" == *-* ]]; then
            start=${part%-*}
            end=${part#*-}
            for ((i = start; i <= end; i++)); do
                echo "$i"
            done
        else
            echo "$part"
        fi
    done
}

# Keep the lower id of each SMT pair so we only use physical cores.
_physical_cpus_on_node() {
    local node=$1
    local cpu sib kept=""
    local -A seen=()
    while read -r cpu; do
        sib=$(cat "/sys/devices/system/cpu/cpu${cpu}/topology/thread_siblings_list")
        sib=${sib%%,*}
        sib=${sib%%-*}
        if [[ -z ${seen[$sib]+x} ]]; then
            seen[$sib]=1
            kept+="${sib},"
        fi
    done < <(_expand_cpulist "$(cat "/sys/devices/system/node/node${node}/cpulist")")
    echo "${kept%,}"
}

_to_range() {
    # 0,1,2,3 → 0-3 when contiguous; otherwise leave as a csv list.
    local csv=$1
    local first last prev n
    IFS=',' read -ra ids <<< "$csv"
    first=${ids[0]}
    last=${ids[-1]}
    prev=$first
    for n in "${ids[@]:1}"; do
        if (( n != prev + 1 )); then
            echo "$csv"
            return
        fi
        prev=$n
    done
    echo "${first}-${last}"
}

if [[ ! -d /sys/devices/system/node/node${NUMA_NODE_SERVER} ]]; then
    echo "NUMA node ${NUMA_NODE_SERVER} not found" >&2
    exit 1
fi

SERVER_CPUSET=$(_to_range "$(_physical_cpus_on_node "$NUMA_NODE_SERVER")")
CLIENT_CPUSET=$(_to_range "$(_physical_cpus_on_node "$NUMA_NODE_CLIENT")")
SERVER_MEMS=$NUMA_NODE_SERVER
CLIENT_MEMS=$NUMA_NODE_CLIENT
# Leave a little of the ~128 GiB node for the kernel and page cache.
SERVER_MEMORY=${SERVER_MEMORY:-110g}
SERVER_CPU_COUNT=$(echo "$SERVER_CPUSET" | awk -F- '{ if (NF==2) print $2-$1+1; else print gsub(/,/,",")+1 }')

export NUMA_NODE_SERVER NUMA_NODE_CLIENT
export SERVER_CPUSET CLIENT_CPUSET SERVER_MEMS CLIENT_MEMS
export SERVER_MEMORY SERVER_CPU_COUNT
export QDRANT_OPTIMIZER_CPU_BUDGET=${QDRANT_OPTIMIZER_CPU_BUDGET:-$SERVER_CPU_COUNT}
export QDRANT_MAX_SEARCH_THREADS=${QDRANT_MAX_SEARCH_THREADS:-$SERVER_CPU_COUNT}

if [[ "${1:-}" == "--print" ]]; then
    echo "server  cpus=${SERVER_CPUSET} mems=${SERVER_MEMS} memory=${SERVER_MEMORY} threads=${SERVER_CPU_COUNT}"
    echo "client  cpus=${CLIENT_CPUSET} mems=${CLIENT_MEMS}"
fi
