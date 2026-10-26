# Matched HNSW grid vs tuned configs

Use this note when someone asks: *“Qdrant can be tuned for max RPS — did you do that? Why not give each engine its best knobs?”*

**Short answer.** This rematch did **not** tune Qdrant for max RPS. It also did **not** use each vendor’s stock defaults. Every engine ran the **same HNSW grid**. The precision-floor table then picks each engine’s best cell *on that grid*. That is the only comparison that stays apples-to-apples.

A “vendor-best / max-RPS” suite is a valid *follow-up*, not a replacement. Mixing those cells into this report would make the first publish weaker.

---

## What this run used

Config: [`experiments/configurations/greenfield-hnsw.json`](../experiments/configurations/greenfield-hnsw.json).

| Knob | Values | Applied as |
| --- | --- | --- |
| `m` / max connections | 16, 32, 64 | Qdrant `hnsw_config.m`, Weaviate `maxConnections`, Milvus `M`, ES/OS `m`, Redis `M` |
| `ef_construct` | 100, 200, 500, 1000 | matching construct knobs |
| search `ef` | 100, 200, 500, 1000 | `hnsw_ef` / `ef` / `num_candidates` / Redis `EF` |
| client parallelism | 1 and 100 | latency vs RPS |
| upload parallelism | 16 | same for all |

No binary or scalar quantization. No rescore. No oversampling. No on-disk HNSW. No extra replicas or shards.

Those knobs exist in this repo for **Qdrant** (`qdrant-quantizations.json`, `qdrant-single-node-bq-rps.json`, `qdrant-single-node-sq-rps.json`, `qdrant-on-disk.json`). They were left out of the rematch on purpose.

### What *is* Qdrant-specific (not an RPS product tune)

- `memmap_threshold: 10_000_000` so the collection stays in RAM
- `on_disk: false` on vectors
- `QDRANT_MAX_SEARCH_THREADS` / optimizer budget = 32, matching the NUMA-pinned socket

Every other engine got the same 32-core / 110 GiB pin via cgroup. Search-thread count is just the Qdrant env hook for that pin.

So the RPS gap vs Redis / Weaviate is **on a matched HNSW graph**, not “defaults vs a tuned Qdrant.”

---

## Why a tuned benchmark is hard

The hard part is the comparison rule, not the scripts. You can run tuned cells in a few days. You cannot make those cells “the same HNSW graph” without lying a little.

Each engine’s real speed knobs are different objects:

| Class | Qdrant | Others (uneven) |
| --- | --- | --- |
| Quantization | scalar int8, binary, rescore, oversampling — already in-repo | Weaviate PQ/BQ, Milvus IVF_PQ / SQ / DiskANN, ES/OS `int8` / BBQ, Redis `QUANTIZATION`, pgvector has almost nothing |
| Memory vs disk | mmap / on-disk HNSW already in-repo | Milvus and OpenSearch have some on-disk JSON; the rest do not |
| Serving | search threads, segments, replicas | each compose file is a different surface |

This framework already expresses Qdrant’s tune better than anyone else’s. If you only turn those Qdrant files on, Qdrant will look better because more engineering time was spent on Qdrant. That is the bias reviewers will (correctly) call.

Binary quantization in Qdrant is not the same object as Weaviate BQ or Milvus SQ. Rescore + oversample has no Redis equivalent. A Redis cell that wins RPS at 0.67 recall is not the same product as a Qdrant BQ cell at 0.95 with rescore. Flattening that into one trophy table is not apples-to-apples.

---

## Three defensible designs

In order of honesty:

1. **Best effort at a recall floor (recommended follow-up).** For each engine, allow a small, documented menu of *that engine’s* real knobs. Rank only at precision ≥ X. Title it “vendor-best at 0.95,” not “same index.” Publish the exact winning config. Engineering: medium. One good cell per engine × dataset, not a 12-point grid.
2. **Capability classes.** Three separate reports: raw HNSW (this rematch), scalar/int8, binary. An engine that lacks a class is absent from that report, not scored as zero. Engineering: medium-high. Comparison stays honest.
3. **One giant mixed table.** Fast to draw, impossible to defend. Do not do this for a published report.

---

## Effort if we pursue a tuned follow-up

- Wiring Qdrant BQ/SQ: easy — the JSON is already here.
- Wiring the others: the work. Client `collection_params` / `search_params` for Weaviate compression, Milvus index types, ES/OS `int8`, Redis quantization. Some of that exists in older single-node configs; it is not a clean 7-engine matrix.
- Time: **1–2 days** to stand up a curated “one tuned cell per engine” if the knobs are already known; **about a week** if they have to be discovered; **another 1–2 days** of wall-clock on this metal for the four core datasets.
- A full cross-product of tunes would be another overnight-sized suite.

Do **not** fold tuned cells into the Wednesday grid or the current slider. That mixes “same graph” with “best product.” Ship the matched grid. Treat tuned configs as a labeled appendix: same host, same datasets, same precision floor, different knobs, configs listed.

The slider on [`docs/visual/index.html`](visual/index.html) is the right primitive for both reports. The tuned one only changes *which cells are allowed into the pool*.

---

## One-liner for review

> We compared the same HNSW knobs on the same host. We did not give Qdrant quantization or other RPS-only features. A vendor-best suite is a follow-up and will be labeled as such; it is not a fair substitute for this grid.
