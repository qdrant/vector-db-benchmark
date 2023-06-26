#!/bin/bash

set -e

mkdir projects

# Install docker

apt-get update
apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

mkdir -p /etc/apt/keyrings

curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update

apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

docker run hello-world

# Optionally change the directory

#DOCKER_CHROOT=/mnt/HC_Volume_23896067


DOCKER_CHROOT=${DOCKER_CHROOT:-}


# check if DOCKER_CHROOT is set

if [ -z "$DOCKER_CHROOT" ]; then
    echo "DOCKER_CHROOT is not set"
else
    docker rm -f $(docker ps -aq); docker rmi -f $(docker images -q)
    systemctl stop docker
    rm -rf /var/lib/docker
    mkdir /var/lib/docker
    mkdir ${DOCKER_CHROOT}/docker
    mount --rbind ${DOCKER_CHROOT}/docker /var/lib/docker
    systemctl start docker
fi

# Python

apt install -y python3-pip python-is-python3

pip install virtualenv

# jq

apt install -y jq

