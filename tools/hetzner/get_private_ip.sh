#!/bin/bash

set -e
# Get ip of the private network interface of Hetzner server
# Using `hcloud` CLI tool

# Usage: ./get_private_ip.sh <server_name>

# Example: ./get_private_ip.sh benchmark-server-1

hcloud server describe "$1" -o json | jq -r '.private_net[0].ip'
