# remote-backend-local-client

This is an example of how to run the server on remote machine, using Docker over
SSH, and remote client instance putting the data into it. It requires the remote
server to have both ssh and Docker daemons running.

The process might be simplified by setting the shell variables beforehand.

```shell
ENGINE_NAME="qdrant-0.8.4"
DATASET_NAME="random-100"
SERVER_BACKEND="remote"
CLIENT_BACKEND="remote"
SERVER_HOST="127.0.0.12"
DOCKER_HOST="ssh://username@$SERVER_HOST"
```

1. Run the server with a remote backend, pointing to the Docker daemon running
   on a remote machine:

    ```shell
    python main.py run-server $ENGINE_NAME \
      --backend-type $SERVER_BACKEND \
      --docker-host $DOCKER_HOST
    ```

   The server process won't finish on its own. It may either fail or be
   interrupted manually.

2. Configure the collection with the dataset specific configuration.

   ```shell
   python main.py run-client $ENGINE_NAME configure $DATASET_NAME \
      --backend-type $CLIENT_BACKEND \
      --server-host $SERVER_HOST \
      --docker-host $DOCKER_HOST
   ```

3. Put all the data defined in the dataset and measure the KPIs.

   ```shell
   python main.py run-client $ENGINE_NAME load $DATASET_NAME \
      --backend-type $CLIENT_BACKEND \
      --server-host $SERVER_HOST \
      --docker-host $DOCKER_HOST
   ```
