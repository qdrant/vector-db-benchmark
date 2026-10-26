# Green-field vector-DB rematch — experiment plan

Date: 24 October 2026
Host: AWS `c6id.metal` (this machine)
Branch: `feat/latest-engine-versions`
Runner: `tools/run_overnight.sh` → `run_all_engines.sh`

This is a **green-field** suite. It does **not** try to reproduce the 2024
[qdrant.tech/benchmarks](https://qdrant.tech/benchmarks) Azure numbers
(8 vCPU / 25 GiB). Those published figures used a different SKU, older
engine builds, and no NUMA isolation. This run measures latest engine
versions on one socket of this metal, with the client isolated on the
other socket.

**Soft deadline:** end of Wednesday 28 October 2026, Pacific (PDT).

---

## 0. Publication plan

Ship a clean first report from the four ANN datasets that have official
ground truth. FineWeb is a nice-to-have and is **not** required for that
publish. Any FineWeb JSON already on disk stays; more can be appended
after the first report.

| Phase | Datasets | Engines | Precision | When |
| --- | --- | --- | --- | --- |
| **First published report** | glove, gist, dbpedia, cohere | all 7 | scored | by Wednesday EOD Pacific |
| **Appendix** | FineWeb-1M (`fineweb-10b-dense-1m`) | engines that accept UUID ids | not scored (no official GT on the 1M slice) | after the core grid; optional |
| Later | filter-recall suite | all 7 | scored where GT exists | not started |

`tools/run_overnight.sh` runs those phases in that order. FineWeb is
gated behind `RUN_FINEWEB=1` and is not added just because
`FINEWEB_10B_DIR` is set.

---

## 1. Goal

Compare seven engines on the same HNSW grid, same **core** datasets,
same host SKU, and the same NUMA pin:

| Question | How it is answered |
| --- | --- |
| Index build cost | Upload / import time in the `*-upload-*.json` results |
| Single-thread latency | Search at `parallel=1` for each `ef` |
| Saturated RPS | Search at `parallel=100` for each `ef` |
| Quality vs speed | Precision is scored on glove / gist / dbpedia / cohere. FineWeb-1M (appendix) does **not** score precision — official GT is for the full 10B corpus. |

A later **filter-recall** suite is defined but is **not** part of the
overnight run. See [§8](#8-planned-follow-up-filter-recall).

---

## 2. Host SKU

| | |
| --- | --- |
| Instance | `c6id.metal` |
| CPU | Intel Xeon Platinum 8375C |
| Sockets / NUMA | 2 nodes |
| Cores | 32 physical cores + SMT per node |
| Memory | ~128 GiB per node, 251 GiB total |
| Scratch | Instance store plus 5 TB at `/mnt/benchmark` (`nvme5n1p1`) |

### NUMA pin (`tools/numa_env.sh`, `tools/pin_docker_numa.sh`)

Cross-node memory distance on this box is about 2×. The pin keeps the
server and the client on opposite sockets and leaves SMT unused so a
search thread cannot share a physical core.

| Role | NUMA node | Physical CPUs | Memory |
| --- | --- | --- | --- |
| Engine container | 0 | `0-31` | local, cgroup limit `110g` |
| Benchmark client | 1 | `32-63` | local (`numactl --membind=1`) |

The client is the conda env `benchmark` (`BENCHMARK_PYTHON`).
`QDRANT_OPTIMIZER_CPU_BUDGET` and `QDRANT_MAX_SEARCH_THREADS` are set to
32 (physical cores on the server node).

---

## 3. Engines (latest pins)

Single-node Docker Compose under `engine/servers/*-single-node/`.

| Engine | Image | Client library |
| --- | --- | --- |
| Qdrant | `qdrant/qdrant:v1.20.0` | `qdrant-client` (dev branch) |
| Weaviate | `cr.weaviate.io/semitechnologies/weaviate:1.39.13` | `weaviate-client` ≥4.22,<5 |
| Milvus | `milvusdb/milvus:v3.0.4` + etcd `v3.5.25` + MinIO `RELEASE.2024-12-18T13-15-44Z` | `pymilvus` ^3.0.0 |
| Elasticsearch | `docker.elastic.co/elasticsearch/elasticsearch:9.5.5` | `elasticsearch` ^9.5 |
| OpenSearch | `opensearchproject/opensearch:3.9.0` | `opensearch-py` ^3.2 |
| Redis | `redis:8.10.2` | `redis` ^5.0.1 |
| pgvector | `pgvector/pgvector:0.8.7-pg16` | `psycopg[binary]` ^3.1, `pgvector` ^0.5 |

OpenSearch runs with `DISABLE_SECURITY_PLUGIN=true` (no demo security
config). Elasticsearch / OpenSearch wait for a green or yellow cluster
health before the client starts.

### Known engine limits

- **pgvector** caps `ef_construction` and `hnsw.ef_search` at 1000. The
  grid never exceeds that, so no cell is clipped.
- **Milvus** INT64 ids cannot store FineWeb UUIDs. FineWeb cells raise
  `IncompatibilityError` and are skipped for Milvus (`--no-exit-on-error`).
- FineWeb point IDs are 128-bit UUID ints. Qdrant stores them as UUID
  point IDs; pgvector uses a `TEXT` PK; ES/OpenSearch use hex ids.

---

## 4. HNSW grid

Config file: [`experiments/configurations/greenfield-hnsw.json`](../experiments/configurations/greenfield-hnsw.json)
(84 named cells: 7 engines × 12 index settings).

| Parameter | Values | Notes |
| --- | --- | --- |
| `m` / max connections | 16, 32, 64 | |
| `ef_construct` | 100, 200, 500, 1000 | `ef_construct=10000` was considered and dropped |
| Search `ef` | 100, 200, 500, 1000 | Same set as construct |
| Search parallelism | 1 and 100 | Latency vs RPS |

Naming: `{engine}-m-{m}-ef-{ef_construct}`.

Each cell runs **8** search configs (4 `ef` × 2 parallelisms). Upload
parallelism is 16.

Engine-specific names for the same knobs (`hnsw_config.m`,
`vectorIndexConfig.maxConnections`, `M`, `ef_construction`, …) are
mapped in that JSON so the grid is comparable.

This is a **matched grid**, not vendor defaults and not a max-RPS tune.
Qdrant quantization / rescore / on-disk configs exist in this repo and
were left out on purpose. When asked why, use
[`methodology-matched-vs-tuned.md`](methodology-matched-vs-tuned.md).

---

## 5. Datasets

**First published report (core):** glove, gist, dbpedia, cohere — all
seven engines, full HNSW grid, precision scored. This is the Wednesday
deliverable.

**Appendix (after the core finishes):** FineWeb-1M. Nice-to-have; 100k
queries make one cheap cell ~40 minutes of search (~10 hours per
engine). Results append to the same `results/` dir and are published
later, not in the first report.

| Dataset | Dims | Distance | Size (approx.) | In Wednesday report? |
| --- | --- | --- | --- | --- |
| `glove-100-angular` | 100 | cosine | ANN-Benchmarks glove-100 (~1.18M / 10k queries) | Yes |
| `gist-960-euclidean` | 960 | L2 | ANN-Benchmarks gist (~1M / 1k queries) | Yes |
| `dbpedia-openai-1M-1536-angular` | 1536 | cosine | 1M OpenAI embeddings | Yes |
| `cohere-wiki-1m` | 768 | cosine | 1M Cohere wiki embeddings | Yes |
| `fineweb-10b-dense-1m` | 768 | cosine | First 1M vectors from local FineWeb-10B parquet | Appendix only (no official GT on the slice) |

### FineWeb

Source: [Qdrant/FineWeb-10B](https://huggingface.co/datasets/Qdrant/FineWeb-10B)
(~10.07B docs, 768-d unit-norm dense + sparse mGTE). The Hugging Face
tree is ~46.5 TB and is **not** downloaded.

| Path | Role |
| --- | --- |
| `FINEWEB_10B_DIR=/mnt/benchmark/fineweb/corpus` | Local 1M shard (no S3 at run time). Fallback overlay: `/home/ubuntu/data/fineweb` |
| `FINEWEB_QUERY_DIR=/mnt/benchmark/fineweb` | Query parquet |
| `/mnt/benchmark/fineweb/corpus/train-part0__0047.parquet` | First shard, 1,090,356 × 768-d |
| `/mnt/benchmark/fineweb/bf_k1000_parsed_ids.parquet` | 100k queries: `query_id`, text, 768-d `dense_embedding`, `hit_fineweb_ids` / `hit_fineweb_ids_cleaned` |

The S3 FUSE mount is not used by the overnight run. The 1M shard and
query parquet are staged on NVMe so a token expiry cannot abort the
appendix.

Registered but **not** in the overnight run:

- `fineweb-10b-dense` — full 10B (does not fit: tens of TB of dense vectors vs 251 GiB RAM / ~7 TB free instance store)
- `fineweb-10b-dense-10m` — 10M slice
- `fineweb-10b-sparse`
- `fineweb-10b-dense-text-filters`, `fineweb-10b-dense-structured-filters`

Official top-1000 GT is only valid against the full 10B UUID corpus. The
1M slice sets `skip_ground_truth: true`. Search still uses the 100k
query embeddings; `mean_precision` will be empty.

---

## 6. Workload size

Wednesday report (core):

```
7 engines × 12 HNSW settings × 4 datasets  = 336 configure+upload experiments
336 × 8 search configs                     = 2,688 search runs
```

Appendix (after the core, optional):

```
6 engines × 12 HNSW settings × FineWeb-1M  = 72 configure+upload  (Milvus skipped)
72 × 8 search configs                      = 576 search runs
```

`--skip-if-exists` lets a restart continue without repeating finished
JSON files.

Rough wall-clock on this SKU: **~1.5–2 days remaining** for the core
grid after Qdrant finished (should fit Wednesday EOD Pacific). FineWeb
is about **~10 hours per engine** and is not on the critical path. The
filter suite in §8 is extra (**+2–4 days**) and is not started yet.

---

## 7. How the overnight run is launched

```bash
export BENCHMARK_HOME=/mnt/benchmark
export FINEWEB_10B_DIR=/mnt/benchmark/fineweb/corpus
export FINEWEB_QUERY_DIR=/mnt/benchmark/fineweb
export RUN_PY_ARGS="--skip-if-exists --no-exit-on-error"
tools/run_overnight.sh
```

`run_overnight.sh` downloads glove / gist / dbpedia / cohere into
`/mnt/benchmark/datasets`, then runs `run_all_engines.sh` twice:

1. **Core** — those four datasets, `RUN_FINEWEB=0`.
2. **Appendix** — `fineweb-10b-dense-1m`, `RUN_FINEWEB=1`.

Each engine is started by `tools/run_local_engine.sh`: compose up → wait
for port (and cluster health for ES/OS) → pin cgroup to node 0 →
`numactl` client on node 1 → compose down on exit.

Python is the conda env `benchmark` (resolved by `tools/python_env.sh`).
The project `pyproject.toml` still declares `python = ">=3.10,<3.13"`;
the host env is 3.14, so the client was installed with pip, not Poetry.

Pre-flight: `tools/run_smoke_all_engines.sh` ran `*-m-16-ef-100` on
`random-100` for all seven engines and passed after client/compose
fixes (ES/OS health wait, OpenSearch security flags, pgvector `psycopg`
import, leftover-container cleanup).

---

## 8. Planned follow-up: filter-recall

Not started. Driver: `run_filter_recall.sh`. Same HNSW grid, datasets:

- keyword / int / range / geo paired **with and without** filters
- `arxiv-titles-384-angular-{filters,no-filters}`
- `h-and-m-2048-angular-{filters,no-filters}`
- FineWeb text + structured filters (when those query parquets exist)

This is the “recall cliff” comparison: same index, filtered vs
unfiltered queries.

---

## 9. Outputs

All overnight artifacts stay under `/mnt/benchmark`
(`BENCHMARK_HOME`). Nothing in this suite writes a finished
`plots.html`; the JSON files **are** the machine-readable report.

| Path | Contents |
| --- | --- |
| `/mnt/benchmark/results/` | One JSON per upload or search cell, e.g. `qdrant-m-16-ef-100-glove-100-angular-search-0-….json` |
| `/mnt/benchmark/monitoring/docker.stats.jsonl` | Live docker stats for the current engine (moved to `monitoring/results/` when that engine finishes) |
| `/mnt/benchmark/datasets/` | Downloaded corpora + a copy of `datasets.json` |
| `/mnt/benchmark/fineweb/` | FineWeb query parquet |
| `/mnt/benchmark/logs/` | Overnight pid / log |

Repo-side viewers (run after the suite, pointing at that results dir):

- [`docs/visual/index.html`](visual/index.html) — internal interactive preview (precision-floor table, Pareto, search-`ef` curves, Qdrant comparison). Refresh with `python tools/export_report_data.py`. Not the customer website.
- [`docs/visual/qdrant-comparison.md`](visual/qdrant-comparison.md) — strengths / weaknesses write-up for the current snapshot
- [`docs/methodology-matched-vs-tuned.md`](methodology-matched-vs-tuned.md) — why this is a matched HNSW grid, not a max-RPS tune
- [`scripts/plots.html`](../scripts/plots.html) — generic Chart.js drop-zone
- [`scripts/process-benchmarks.ipynb`](../scripts/process-benchmarks.ipynb) — export in the qdrant.tech single-node format

Smoke JSON from before `BENCHMARK_HOME` was set also exists under the
repo `results/` directory. Treat `/mnt/benchmark/results` as canonical
for the rematch.

---

## 10. Out of scope

- Matching 2024 Azure published RPS / latency
- `ef_construct = 10000`
- Vendor-best / max-RPS tunes (quantization, rescore, on-disk) in the **first** report — see [`methodology-matched-vs-tuned.md`](methodology-matched-vs-tuned.md)
- FineWeb in the **first** published report (appendix only)
- Full FineWeb-10B or the 10M slice
- Sparse FineWeb
- Cluster / multi-node engine topologies
- SMT-on or cross-NUMA “whole box” runs

---

## 11. Reproduce one cell

```bash
export BENCHMARK_HOME=/mnt/benchmark
export FINEWEB_10B_DIR=/mnt/benchmark/fineweb/corpus
export FINEWEB_QUERY_DIR=/mnt/benchmark/fineweb
tools/run_local_engine.sh qdrant-single-node qdrant-m-16-ef-100 glove-100-angular
```

Configs live in `experiments/configurations/greenfield-hnsw.json`.
Dataset definitions live in `datasets/datasets.json`.
