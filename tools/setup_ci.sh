#!/bin/bash

# Set up dependencies

set -euo pipefail

# apt can wedge indefinitely on a dpkg lock or a stalled mirror.
apt_get() { sudo timeout 300 apt-get "$@"; }

apt_get update || echo "apt-get update failed, continuing with the cached package list" >&2
apt_get install -y jq

# Download and install hcloud

HCVERSION=v1.36.0

wget --timeout=30 --tries=3 https://github.com/hetznercloud/cli/releases/download/${HCVERSION}/hcloud-linux-amd64.tar.gz

tar xzf hcloud-linux-amd64.tar.gz

sudo mv hcloud /usr/local/bin
