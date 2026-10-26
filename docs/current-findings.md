# Current findings — green-field rematch

Snapshot: 24 October 2026, 17:20 UTC  
Host: AWS `c6id.metal`, NUMA-pinned (engine CPUs `0-31` / 110 GiB; client CPUs `32-63`)  
Results: `/mnt/benchmark/results`  
Plan: [`experiment-plan.md`](experiment-plan.md)

**Soft deadline:** end of Wednesday 28 October 2026, Pacific (PDT).

The suite is **still running**. These numbers are from finished JSON
cells only. They are **not** comparable to the 2024 Azure 8 vCPU / 25 GiB
published charts.

---

## Publication plan

| Ship | Contents | Status |
| --- | --- | --- |
| **First published report** (Wednesday) | glove, gist, dbpedia, cohere × 7 engines × full HNSW grid. Precision scored. | In progress. Qdrant complete. Weaviate almost complete except cohere. Five engines not started. |
| **Appendix** (after that report) | FineWeb-1M latency / RPS. No official GT on the 1M slice. | Nice-to-have. Partial Qdrant cells stay on disk; the runner starts FineWeb only after the core grid. |

Do not wait on FineWeb to publish. Append those JSON files later.

---

## 1. Coverage — Wednesday report

12 HNSW cells × 8 search configs = 96 searches per engine × dataset.

| Engine | glove | gist | dbpedia | cohere | Notes |
| --- | --- | --- | --- | --- | --- |
| Qdrant | 12 / 96 | 12 / 96 | 12 / 96 | 12 / 96 | **complete** |
| Weaviate | 11 / 88 | 11 / 88 | 11 / 83 | 0 / 0 | Uploading leftover `m-64-ef-500` dbpedia. `m-64-ef-1000` not started. **cohere upload fails** on reserved `id` property |
| Milvus, Elasticsearch, OpenSearch, Redis, pgvector | — | — | — | — | Not started |

Core search JSON files (excluding smoke and FineWeb): **643**. Core
uploads: **81**.

---

## 2. Headline: `m=16`, `ef_construct=100`, search `ef=100`

Single-thread latency (`parallel=1`) and saturated RPS (`parallel=100`).
Core datasets only.

| Dataset | Engine | Precision | p95 (`p=1`) | RPS (`p=1`) | RPS (`p=100`) |
| --- | --- | ---: | ---: | ---: | ---: |
| glove-100 (cosine, ~1.18M × 100d) | Qdrant | **0.845** | 2.89 ms | 461 | 8,744 |
| glove-100 | Weaviate | 0.671 | 3.06 ms | 432 | **13,728** |
| gist-960 (L2, ~1M × 960d) | Qdrant | **0.893** | 3.32 ms | 363 | 2,174 |
| gist-960 | Weaviate | 0.664 | 3.70 ms | 344 | **6,075** |
| dbpedia-1M (cosine, 1536d) | Qdrant | **0.985** | 2.97 ms | 441 | 1,891 |
| dbpedia-1M | Weaviate | 0.959 | 3.16 ms | 405 | **8,002** |
| cohere-wiki-1M (cosine, 768d) | Qdrant | 0.983 | 3.18 ms | 372 | 3,069 |
| cohere-wiki-1M | Weaviate | — | — | — | upload interrupted, no numbers |

**Read this as two different wins, not one winner.** At this cheap HNSW
setting Weaviate posts much higher saturated RPS and worse recall.
Qdrant is a bit faster single-thread and holds higher precision on every
dataset that both finished.

---

## 3. Same index, raise search `ef` (glove, `m=16` / `ef_construct=100`)

| search `ef` | Qdrant prec / p95 (`p=1`) / RPS (`p=100`) | Weaviate prec / p95 (`p=1`) / RPS (`p=100`) |
| ---: | --- | --- |
| 100 | 0.845 / 2.89 ms / 8,744 | 0.671 / 3.06 ms / 13,728 |
| 200 | 0.903 / 3.03 ms / 5,630 | 0.758 / 3.74 ms / 11,585 |
| 500 | 0.957 / 3.84 ms / 2,792 | 0.845 / 5.10 ms / 7,461 |
| 1000 | **0.981** / 5.00 ms / 1,583 | 0.897 / 7.52 ms / 4,739 |

Weaviate never catches Qdrant’s glove recall in this cell, even at
`ef=1000` (0.897 vs 0.981). Its RPS stays higher as `ef` grows.

---

## 4. Qdrant HNSW grid on glove (search `ef=100`)

Precision climbs with `m` and `ef_construct`; saturated RPS falls.
Single-thread p95 stays ~3 ms across the grid.

| m | ef_construct | Precision | p95 (`p=1`) | RPS (`p=100`) |
| ---: | ---: | ---: | ---: | ---: |
| 16 | 100 | 0.845 | 2.89 ms | 8,744 |
| 16 | 200 | 0.861 | 2.83 ms | 8,265 |
| 16 | 500 | 0.868 | 2.92 ms | 7,964 |
| 16 | 1000 | 0.869 | 2.93 ms | 7,081 |
| 32 | 100 | 0.886 | 2.94 ms | 6,975 |
| 32 | 200 | 0.910 | 3.00 ms | 5,891 |
| 32 | 500 | 0.923 | 3.10 ms | 5,111 |
| 32 | 1000 | 0.924 | 3.01 ms | 4,850 |
| 64 | 100 | 0.903 | 3.01 ms | 5,987 |
| 64 | 200 | 0.933 | 3.15 ms | 4,790 |
| 64 | 500 | 0.952 | 3.22 ms | 3,891 |
| 64 | 1000 | **0.957** | 3.30 ms | 3,382 |

On glove, raising `ef_construct` at `m=16` barely moves recall
(0.845 → 0.869). Raising `m` does more. Highest glove recall in the
finished Qdrant grid at search `ef=100` is **0.957** (`m=64`,
`ef_construct=1000`).

---

## 5. Index build cost (`m=16`, `ef_construct=100`)

`upload_time` is insert; `total_time` includes HNSW optimization
(Qdrant). Weaviate reports them as the same value.

| Dataset | Qdrant insert / total | Weaviate total |
| --- | --- | --- |
| glove-100 | 17 s / 42 s | 60 s |
| gist-960 | 79 s / 154 s | 88 s |
| dbpedia-1M | 99 s / 214 s | 112 s |
| cohere-1M | 61 s / 131 s | failed |

Heavier construct is expensive. Qdrant dbpedia `m=64` /
`ef_construct=1000` is **1,182 s** total vs **214 s** at `m=16` /
`ef_construct=100`. Weaviate dbpedia `m=32` / `ef_construct=1000` is
**879 s**.

---

## 6. Gaps that affect the Wednesday report

- **Weaviate + cohere-wiki-1m**: uploads failed on reserved payload `id`.
  Client now drops reserved / undeclared properties. Restart will retry
  those cells.
- **Weaviate leftover cells**: `m-64-ef-500` dbpedia search 0–2 only from
  the earlier crash; the current job is re-uploading that cell.
  `m-64-ef-1000` not started.
- **Milvus, Elasticsearch, OpenSearch, Redis, pgvector**: no core numbers
  yet. These are the remaining Wednesday work.
- Filter-recall suite: not started; not in the first report.

---

## 7. What the first report will *not* say

Five engines have no numbers yet. Weaviate is missing its last HNSW cell
and all of cohere. Do not treat the Weaviate RPS advantage at low recall
as a final ranking. FineWeb is out of this report.

Raw JSON remains the source of truth: `/mnt/benchmark/results`.

---

## Appendix — FineWeb-1M (nice-to-have, publish later)

Not part of the Wednesday report. Qdrant `m-16-ef-100` is complete;
`m-16-ef-200` is partial (2 uploads, 10 searches). Other engines have
not started. The overnight runner reaches this only after the core
grid.

Local shard: `/mnt/benchmark/fineweb/corpus/train-part0__0047.parquet`
(1,090,356 × 768-d). Queries: 100k from
`/mnt/benchmark/fineweb/bf_k1000_parsed_ids.parquet`.

`mean_precisions=1.0` in the JSON is **not real recall**. Official GT is
for the full 10B corpus; the 1M slice sets `skip_ground_truth`. Treat
FineWeb as latency / RPS only.

| Stage (Qdrant `m-16-ef-100`) | Result |
| --- | --- |
| Insert | 289 s |
| Insert + optimize | 359 s |
| Search `ef=100`, `p=1` | 454 RPS, p95 2.78 ms |
| Search `ef=200`, `p=1` | 329 RPS, p95 3.64 ms |
| Search `ef=500/1000` and `p=100` | not written yet |

Milvus FineWeb is a planned skip (INT64 ids cannot store UUIDs).
