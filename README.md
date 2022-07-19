# vector-db-benchmark

There are various vector search engines available, and each of them may offer
a different set of features and efficiency. But how do we measure the
performance? There is no clear definition and in a specific case you may worry
about a specific thing, while not paying much attention to other aspects. This
project is a general framework for benchmarking different engines under the
same hardware constraints, so you can choose what works best for you.

Running any benchmark requires choosing an engine, a dataset and the scenario
against which it should be tested.

## TL;DR

```shell
python main.py \
  --engine qdrant-0.8.4 \
  --scenario scenario.load.MeasureLoadTimeSingleClient \
  --dataset random-100
```

Will execute the benchmark scenario enclosed in a
`scenario.load.MeasureLoadTimeSingleClient` class and use a `random-100`
dataset. All the operation will be launched on a `qdrant-0.8.4` engine.

Expected output should look like following:

```shell
mean(load::time) = 0.0015927800000000007
```

### Backend

A specific way of managing the containers. Right now only Docker, but might be
Docker Swarm or Kubernetes, so the benchmark is not executed on a single
machine, but on several servers.

### Engine

There are various vector search projects available. Some of them are just pure
libraries (like FAISS or Annoy) and they offer great performance, but doesn't
fit well any production systems. Those could be also benchmarked, however the
primary focus is on vector databases using client-server architecture.

All the engine configurations are kept in `./engine` subdirectories.

Each engine has its own configuration defined in `config.json` file:

```json
{
  "server": {
    "image": "qdrant/qdrant:v0.8.4",
    "hostname": "qdrant_server",
    "environment": {
      "DEBUG": true
    }
  },
  "client": {
    "dockerfile": "client.Dockerfile",
    "main": "python cmd.py"
  }
}
```

- Either `image` or `dockerfile` has to be defined, similar to
  `docker-compose.yaml` file. The `dockerfile` has a precedence over `image`
- The `main` parameter points to a main client script which takes parameters.
  Those parameters define the operations to perform with a client library.

#### Server

The server is a process, or a bunch of processes, responsible for creating
vector indexes and handling all the user requests. It may be run on a single
machine, or in case of some engines using the distributed mode (**in the future**).

#### Client

A client process performing all the operations, as it would be typically done in
any client-server based communication. There might be several clients launched
in parallel and each of them might be using part of the data. The number of
clients depends on the scenario.

Each client has to define a main script which takes some parameters and allow
performing typical CRUD-like operations. For now there is only one operation
supported:

- `load [path-to-file]`

If the scenario attempts to load the data from a given file, then it will call
the following command:

`python cmd.py load vectors.jsonl`

The main script has to handle the conversion and load operations.

By introducing a main script, we can allow using different client libraries, if
available, so there is no assumption about the language used, as long as it can
accept parameters.

### Dataset

Consists of vectors and/or payloads. Scenario decides what to do with the data.

## Metrics

Metrics are being measured by the clients themselves and displayed on stdout.
The benchmark will collect all the metrics and display some statistics at the
end of each test.

All the displayed metrics should be printed in the following way:

```shell
phase::kpi_name = 0.242142
```

Where `0.242142` is a numerical value specific for the `kpi_name`. In the
simplest case that might be a time spent in a specific operation, like:

```
load::time = 0.0052424
```

## Open topics

1. The list of supported KPIs should be still established and implemented by
   every single engine, so can be tracked in all the benchmark scenarios.
2. What should be the format supported in the datasets? JSON lines are cross
   language and platform, what makes them easy to be parsed to whatever format
   a specific engine support.
3. Should the scenario be tightly-coupled with the dataset or allow using
   different datasets? For simpler cases that may work, but there might be some
   specific problems that won't be possible for each dataset.
4. How do we handle engine errors?
5. The dataset should also have a file-based config, like engine.
