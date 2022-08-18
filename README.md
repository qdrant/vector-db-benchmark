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


### Run the client



## How to update benchmark parameters?

## How to register a dataset?

## How to implement a new engine?

