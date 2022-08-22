# vector-db-benchmark

There are various vector search engines available, and each of them may offer
a different set of features and efficiency. But how do we measure the
performance? There is no clear definition and in a specific case you may worry
about a specific thing, while not paying much attention to other aspects. This
project is a general framework for benchmarking different engines under the
same hardware constraints, so you can choose what works best for you.

Running any benchmark requires choosing an engine, a dataset and defining the
scenario against which it should be tested. A specific scenario may assume
running the server in a single or distributed mode, a different client
implementation and the number of client instances.

## How to run a benchmark?

Benchmarks are implemented in server-client mode, meaning that the server is
running in a single machine, and the client is running on another.

### Run the server

All engines are served using docker compose. The configuration is in the [servers](./engine/servers/).

To launch the server instance, run the following command:

```bash
cd ./engine/servers/<engine-configuration-name>
docker compose up
```

Containers are expected to expose all necessary ports, so the client can connect to them.

### Run the client

Install dependencies:

```bash
pip install poetry
poetry install
```

Run the benchmark:

```bash
Usage: run.py [OPTIONS]

  Example: python3 run --engines *-m-16-* --datasets glove-*

Options:
  --engines TEXT                  [default: *]
  --datasets TEXT                 [default: *]
  --host TEXT                     [default: localhost]
  --skip-upload / --no-skip-upload
                                  [default: no-skip-upload]
  --install-completion            Install completion for the current shell.
  --show-completion               Show completion for the current shell, to
                                  copy it or customize the installation.
  --help                          Show this message and exit.
```

Command allows you to specify wildcards for engines and datasets.
Results of the benchmarks are stored in the `./results/` directory.

## How to update benchmark parameters?

Each engine has a configuration file, which is used to define the parameters for the benchmark.
Configuration files are located in the [configuration](./experiments/configurations/) directory.

Each step in the benchmark process is using a dedicated configuration's path:

* `connection_params` - passed to the client during the connection phase.
* `collection_params` - parameters, used to create the collection, indexing parameters are usually defined here.
* `upload_params` - parameters, used to upload the data to the server.
* `search_params` - passed to the client during the search phase. Framework allows multiple search configurations for the same experiment run.

Exact values of the parameters are individual for each engine.

## How to register a dataset?

Datasets are configured in the [datasets/datasets.json](./datasets/datasets.json) file.
Framework will automatically download the dataset and store it in the [datasets](./datasets/) directory.

## How to implement a new engine?

There are a few base classes that you can use to implement a new engine.

* `BaseConfigurator` - defines methods to create collections, setup indexing parameters.
* `BaseUploader` - defines methods to upload the data to the server.
* `BaseSearcher` - defines methods to search the data.

See the examples in the [clients](./engine/clients) directory.

Once all the necessary classes are implemented, you can register the engine in the [ClientFactory](./engine/clients/client_factory.py).

