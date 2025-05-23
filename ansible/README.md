## How to run

### Prerequisites
* ssh keys (to connect to the remote machines)
* inventory.ini (to define the actual machine on which the benchmark is run)

Add inventory.ini in [ansible/playbooks/](playbooks) with the following content:
```ini
[remote_machines]
benchmark-machine ansible_host=${YOUR_SERVER_IP} ansible_user=${YOUR_USER}
[db_hosts]
benchmark-db ansible_host=${YOUR_SERVER_IP} ansible_user=${YOUR_USER}
```

### Run ansible inside Docker
Ensure the ssh keys are properly mounted into the container.

Run the following commands from [ansible](.):
```bash
docker buildx build --tag vector-db-benchmark-ansible:latest -f Dockerfile .
docker run --rm -it -v ~/.ssh/id_rsa:/root/.ssh/id_rsa -v ~/.ssh/id_rsa.pub:/root/.ssh/id_rsa.pub -v ./playbooks:/ansible/playbooks vector-db-benchmark-ansible ansible-playbook playbook-hnsw-index.yml --extra-vars "bench=002"
```

### Run ansible locally
The "local" run here means that the ansible command is run locally (so, Ansible should be installed locally).
The actual machine on which the benchmark is run is defined by the inventory file (see Prerequisites).

Run the following commands from [ansible/playbooks](playbooks):
```bash
ansible-playbook playbook-hnsw-index.yml --extra-vars "bench=002"
```