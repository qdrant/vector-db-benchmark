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
docker run --rm -it -v ~/.ssh/id_rsa:/root/.ssh/id_rsa -v ~/.ssh/id_rsa.pub:/root/.ssh/id_rsa.pub -v ./playbooks:/ansible/playbooks vector-db-benchmark-ansible ansible-playbook playbook-hnsw-index.yml --extra-vars "bench=update"
```

### Run ansible locally
The "local" run here means that the ansible command is run locally (so, Ansible should be installed locally).
The actual machine on which the benchmark is run is defined by the inventory file (see Prerequisites).

Run the following commands from [ansible/playbooks](playbooks):
```bash
ansible-playbook playbook-hnsw-index.yml --extra-vars "bench=update"
```

## How to add a new benchmark

* Create a new playbook in the [ansible/playbooks](playbooks) directory (i.e `playbook-hnsw-index.yml`). The playbook defines which role to run on which machine (i.e run `run-hnsw-indexing-update` on machines of `remote_machines` group).
* Add a new folder in [ansible/playbooks/roles](playbooks/roles) (i.e `run-hnsw-indexing-update`) with 2 sub-folders `tasks` (required) and `files` (optional).  Add `main.yml` in `tasks` folder. The role defines tasks (`main.yml`) required to run the benchmark. For example, copying scripts, setting up benchmark server, running the benchmark.
* Optionally in the [ansible/playbooks/group_vars](playbooks/group_vars) directory add a new yml file to define variables specific for the role (i.e `hnsw-indexing-update.yml`). Variables that are shared can also be defined here (i.e in `common_vars.yml`).
* Optionally in the [ansible/playbooks/files](playbooks/files) directory add files that are common across several roles and/or playbooks.