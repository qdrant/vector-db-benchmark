# Apache Cassandra®

## Setup
### Pre-requisites
Adjust the configuration file [`cassandra-single-node.json`](../../../experiments/configurations/cassandra-single-node.json) to your needs. The default configuration is set to use the default Apache Cassandra® settings.
### Start up the server
Run the following command to start the server (alternatively, run `docker compose up -d` to run in detached mode):
```bash
$ docker compose up

[+] Running 1/1
 ✔ cassandra Pulled                                                                                                                                                                           1.4s 
[+] Running 1/1
 ✔ Container cassandra-benchmark  Recreated                                                                                                                                                   0.1s 
Attaching to cassandra-benchmark
cassandra-benchmark  | CompileCommand: dontinline org/apache/cassandra/db/Columns$Serializer.deserializeLargeSubset(Lorg/apache/cassandra/io/util/DataInputPlus;Lorg/apache/cassandra/db/Columns;I)Lorg/apache/cassandra/db/Columns; bool dontinline = true
...
cassandra-benchmark  | INFO  [main] 2025-04-04 22:27:38,592 StorageService.java:957 - Cassandra version: 5.0.3
cassandra-benchmark  | INFO  [main] 2025-04-04 22:27:38,592 StorageService.java:958 - Git SHA: b0226c8ea122c3e5ea8680efb0744d33924fd732
cassandra-benchmark  | INFO  [main] 2025-04-04 22:27:38,592 StorageService.java:959 - CQL version: 3.4.7
...
cassandra-benchmark  | INFO  [main] 2025-04-04 22:28:25,091 StorageService.java:3262 - Node /172.18.0.2:7000 state jump to NORMAL
```
> [!TIP]
> Other helpful commands:
> - Run `docker exec -it cassandra-benchmark cqlsh` to access the Cassandra shell.
> - Run `docker compose logs --follow --tail 10` to view & follow the logs of the container running Cassandra.

### Start up the client benchmark
Run the following command to start the client benchmark using `glove-25-angular` dataset as an example:
```bash
% python3 -m run --engines cassandra-single-node --datasets glove-25-angular 
```
and you'll see the following output:
```bash
Running experiment: cassandra-single-node - glove-25-angular
Downloading http://ann-benchmarks.com/glove-25-angular.hdf5...
...
Experiment stage: Configure
Experiment stage: Upload
1183514it [mm:ss, <...>it/s]
Upload time: <...>
Index is not ready yet, sleeping for 2 minutes...
...
Total import time: <...>
Experiment stage: Search
10000it [mm:ss, <...>it/s]
10000it [mm:ss, <...>it/s]
Experiment stage: Done
Results saved to:  /path/to/repository/results
...
```

> [!TIP]
> If you want to see the detailed results, set environment variable `DETAILED_RESULTS=1` before running the benchmark.