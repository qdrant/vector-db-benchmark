FROM python:3.11-slim

# Set environment variables to prevent prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    sshpass \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir ansible

RUN ansible --version

WORKDIR /ansible/playbooks

CMD ["ansible-playbook", "--version"]