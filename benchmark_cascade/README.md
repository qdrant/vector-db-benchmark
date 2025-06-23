# Benchmark Cascade

Benchmark workflow that runs multiple Qdrant benchmarks in parallel batches on remote machines.

## Configuration

Benchmarks are defined in [benchmark-configs.json](benchmark-configs.json) with predefined sets:
- `smoke_test` - Quick tests (3 benchmarks)
- `full_regression` - Large test suite (30+ benchmarks)
- `single` - A single benchmark configuration

## Running Benchmarks

The workflow accepts these inputs:
* process_results - Boolean flag to control whether to skip all jobs except for the job that processes results.
* workflow_run_ids - Comma-separated list of workflow run IDs to process results from (internal use).
* benchmark_set - Name of the benchmark set to run (e.g., `smoke_test`, `full_regression`, `single`).
* params_override - JSON string to override benchmark parameters (see below for examples)
* current_batch - Current batch index (internal use)
* machines_per_bench - A boolean flag to control whether to run each benchmark on its individual machine or re-use machines.
* machines_info - JSON string with information about machines to use for the benchmarks (internal use).
* max_parallel - Maximum number of parallel jobs to run within one workflow run.

### Option 1: Use Predefined Set
With all the other inputs untouched, run a predefined benchmark set with name `smoke_test`:
```yaml
benchmark_set: smoke_test
```

### Option 2: Single Benchmark
To run just a single benchmark with specific parameters, use the following configuration:
```yaml
benchmark_set: single
params_override: {"params": {"qdrant_version": ["docker/master"], "dataset": ["dbpedia-openai-1M-1536-angular"], "engine_config": ["qdrant-rps-m-16-ef-128"]}}
```

### Option 3: Override Parameters
To run a predefined benchmark set with overridden parameters, use the following configuration:
```yaml
benchmark_set: smoke_test
params_override: {"params": {"qdrant_version": ["ghcr/dev", "docker/v1.12.0"], "dataset": ["glove-100-angular"]}}
```
or
```yaml
benchmark_set: single
params_override: {"params": {"qdrant_version": ["ghcr/hnsw-m-m0", "ghcr/dev"], "dataset": ["dbpedia-openai-1M-1536-angular", "gist-960-euclidean", "glove-100-angular", "deep-image-96-angular"], "engine_config": ["qdrant-rps-m-16-ef-128", "qdrant-rps-m-32-ef-128", "qdrant-rps-m-32-ef-256", "qdrant-rps-m-32-ef-512", "qdrant-rps-m-64-ef-256", "qdrant-rps-m-64-ef-512"]}}
```

## Output

Results are grouped by qdrant version and stored as GitHub artifacts:
- `final_results/results-ghcr-dev.json`
- `final_results/results-docker-v1.12.0.json`

download them from the GitHub Actions page under the latest run.

Use [plots.html](../scripts/plots.html) to visualize the results.
