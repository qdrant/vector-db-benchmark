#!/bin/bash

set -e
# Get public server IP by name

hcloud server ip "$1"
