# vector-db-benchmark

![Screenshot from 2022-08-23 14-10-01](https://user-images.githubusercontent.com/1935623/186516524-a61098d4-bca6-4aeb-acbe-d969cf30674e.png)

> [View results](https://qdrant.tech/benchmarks/)

There are various vector search engines available, and each of them may offer
a different set of features and efficiency. But how do we measure the
performance? There is no clear definition and in a specific case you
may worry about a specific thing, while not paying much attention to other aspects. This
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
$ poetry shell
$ python run.py --help

Usage: run.py [OPTIONS]

  Examples:

  python3 run.py --engines "qdrant-rps-m-*-ef-*" --datasets "dbpedia-openai-100K-1536-angular" # Qdrant RPS mode

  python3 run.py --engines "*-m-*-ef-*" --datasets "glove-*" # All engines and their configs for glove datasets

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

### FineWeb-10B (local parquet)

[Qdrant/FineWeb-10B](https://huggingface.co/datasets/Qdrant/FineWeb-10B) is registered as `fineweb-10b-*` datasets. The Hugging Face corpus is ~46.5 TB and is **not** downloaded by this repo. Point the reader at the parquet you already have:

```bash
export FINEWEB_10B_DIR=/path/to/fineweb-10b   # directory or a single .parquet file
# query embeddings + GT (combined parquet is accepted):
export FINEWEB_QUERY_DIR=/mnt/benchmark/fineweb
export FINEWEB_QUERY_VECTORS=/mnt/benchmark/fineweb/bf_k1000_parsed_ids.parquet
```

Accepted layouts:

* a single corpus parquet file
* the official tree: `data/**/*.parquet` plus `queries/gt_*.parquet`
* query/GT parquet outside the corpus tree (`FINEWEB_QUERY_DIR`, `$BENCHMARK_HOME/fineweb`, or `bf_k1000_parsed_ids.parquet`)

Official top-1000 ground truth is for the full 10B UUID corpus. The `fineweb-10b-dense-1m` / `10m` slices skip precision unless you set `FINEWEB_USE_OFFICIAL_GT=1`. FineWeb is optional: `run_all_engines.sh` adds `fineweb-10b-dense-1m` only when `RUN_FINEWEB=1` and `FINEWEB_10B_DIR` is set. The first published report is glove / gist / dbpedia / cohere; FineWeb appends after that. `run_filter_recall.sh` still adds the filtered FineWeb sets when `FINEWEB_10B_DIR` is set.

## How to implement a new engine?

There are a few base classes that you can use to implement a new engine.

* `BaseConfigurator` - defines methods to create collections, setup indexing parameters.
* `BaseUploader` - defines methods to upload the data to the server.
* `BaseSearcher` - defines methods to search the data.

See the examples in the [clients](./engine/clients) directory.

Once all the necessary classes are implemented, you can register the engine in the [ClientFactory](./engine/clients/client_factory.py).

