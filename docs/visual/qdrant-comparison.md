# How Qdrant compares

Snapshot: 26 October 2026, 16:08 UTC  
Host: AWS `c6id.metal`, NUMA-pinned (engine CPUs `0–31` / client `32–63`)  
Data: [`data.json`](data.json) behind [`index.html`](index.html)  
Plan: [`../experiment-plan.md`](../experiment-plan.md)  
Methodology (matched grid vs tuned RPS): [`../methodology-matched-vs-tuned.md`](../methodology-matched-vs-tuned.md)

Internal preview. Not the customer website. These numbers are **not**
comparable to the 2024 Azure 8 vCPU / 25 GiB charts.

Qdrant, Weaviate, Milvus, Elasticsearch, OpenSearch, and Redis have
finished the four core datasets (glove, gist, dbpedia, cohere).
pgvector is only the first cheap cell on glove and gist. FineWeb is
an appendix and is not in this ranking.

**Qdrant is the default-quality and single-thread latency engine. It
is not the throughput engine.** Redis, Weaviate, and Elasticsearch
usually win saturated RPS once any HNSW cell that clears a recall
floor is allowed.

---

## Same cheap cell

`m=16`, `ef_construct=100`, search `ef=100`.

| Dataset | Qdrant prec / p95 (`p=1`) / RPS (`p=100`) | Closest quality rival | Closest RPS rival |
| --- | --- | --- | --- |
| glove-100 | **0.845** / **2.89 ms** / 8,744 | OpenSearch 0.816, Milvus 0.811 | Redis 18,233 (prec 0.671) |
| gist-960 | 0.893 / **3.32 ms** / 2,174 | OpenSearch 0.875; **Milvus 0.975** | Redis 7,315 (prec 0.664) |
| dbpedia-1M | 0.985 / 2.97 ms / 1,891 | OpenSearch 0.979; **Milvus 0.997** | Redis 8,552 (prec 0.958) |
| cohere-1M | 0.983 / 3.18 ms / 3,069 | OpenSearch 0.970; **Milvus 0.994** | Redis 8,388 (prec 0.909) |

---

## Strengths

**Quality at a cheap index.** On glove, Qdrant’s first cell is already
0.845. Weaviate, Redis, and Elasticsearch sit at ~0.66–0.67. They need
search `ef=500` (Weaviate / Redis) or `ef=1000` (Elasticsearch) on that
same index to catch Qdrant. Elasticsearch never catches Qdrant’s gist
0.893 even at `ef=1000` (0.883).

**Single-thread latency.** p95 is ~3 ms on every core dataset. Redis is
the only peer in that band (and is faster on dbpedia: 2.50 ms). Milvus
and OpenSearch are much slower (dbpedia 17 ms; gist / cohere OpenSearch
22–25 ms).

**Recall ceiling on the HNSW grid.** At search `ef=100`, Qdrant’s best
glove cell is **0.957** (`m=64`, `ef_construct=1000`). Weaviate / Redis
top out around 0.83–0.84; Elasticsearch 0.811. Raising search `ef` on
the cheap glove index takes Qdrant to **0.981** at `ef=1000`; nobody
else breaks 0.93 on that index.

**Stable under load.** Saturated p95 stays usable. OpenSearch glove
jumps to 58 ms, gist 119 ms, dbpedia 220 ms. Milvus gist / cohere at
`p=100` are 167 ms and 345 ms. Qdrant does not have that cliff.

**Index time is fine.** Glove 42 s, in the Redis / Milvus / OpenSearch
group. Elasticsearch is the outlier (glove 304 s, dbpedia 1,181 s).

---

## Weaknesses

**Saturated RPS.** This is the consistent loss. At the cheap cell Redis
is 2.1× Qdrant on glove, 3.4× on gist, 4.5× on dbpedia, 2.7× on cohere
— at lower recall. Even after a recall floor, Qdrant rarely ranks first:

| Floor (RPS, `p=100`) | glove | gist | dbpedia | cohere |
| --- | --- | --- | --- | --- |
| 0.80 | 5th (Redis / Milvus / ES / Weaviate) | 4th | — | — |
| 0.90 | 5th (Milvus / ES / Redis / Weaviate) | 4th | — | 3rd |
| 0.95 | 3rd (Milvus, ES) | 4th | 5th | 3rd |
| 0.98–0.99 | 2nd on glove (Milvus still ahead) | — | 4th–5th | 3rd |

On high-dimensional embeddings (dbpedia, cohere) Redis / Weaviate /
Elasticsearch still deliver **2–4×** Qdrant’s RPS at 0.98–0.99.

**No “sloppy fast” config.** At a 0.70 glove floor, Qdrant is 6th of 7
on RPS because its cheapest cell is already 0.845. Redis / Weaviate /
ES can spend a cheap, low-recall graph and look very fast. That is a
real weakness if the buyer’s bar is “good enough recall, max QPS.”

**Milvus wins raw recall on high-dim.** Cheap-cell gist 0.975 vs 0.893,
dbpedia 0.997 vs 0.985, cohere 0.994 vs 0.983. Qdrant is the better
*balanced* quality engine (Milvus pays with 800 / 460 RPS on gist /
cohere). It is not the recall champion on those sets.

**Not the fastest to index.** Redis and Weaviate finish sooner on
gist / dbpedia / cohere (Redis cohere 52 s vs Qdrant 131 s). Qdrant’s
`total_time` includes HNSW optimize; that is honest, but it is not a
build-speed win.

---

## How to say it

Qdrant if you want high recall from a cheap HNSW graph and low
single-thread latency. Redis or Weaviate if you want max RPS and will
take a lower default recall or a higher search `ef`. Milvus if you want
max recall on 768–1536-d and can live with the load latency.
Elasticsearch is competitive on high-floor RPS and weak on index time
and cheap-cell recall. OpenSearch tracks Qdrant’s recall more closely
than Weaviate does, but is the slow engine under load.

The slider on the [preview](index.html) is the right demo: at 0.80
Qdrant looks mid-pack on RPS; at 0.98 on glove it is in the top two.
That change *is* the comparison.

Refresh numbers after new cells finish:

```bash
python tools/export_report_data.py
```
