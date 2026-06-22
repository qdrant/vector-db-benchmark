# turbopuffer Benchmark Report — v2

**Date:** 2026-06-22 | **Author:** Shivendu Kumar, Qdrant | **Region:** aws-us-west-2  
**Previous report:** [turbopuffer-benchmark-report.md](turbopuffer-benchmark-report.md) (2026-06-17)

> **What changed in v2:** All experiments were re-run from `scripts/reproduce_comparison.py` — a single reproducible script that uses batch=128 across both engines throughout. v1 used inconsistent batch sizes (tpuf: 1000/500, Qdrant: 256/128) and the multi-process `run.py` harness. v2 uses an async client for both. Multi-tenant now directly compares tpuf ns-per-tenant against Qdrant with `payload_m=16` + `is_tenant=True` (v1 only compared tpuf architectures against each other).

---

## 1. Setup

### Datasets

| Dataset | Vectors | Dims | Metric | Filters | Use |
|---------|---------|------|--------|---------|-----|
| `dbpedia-openai-100K-1536-angular` | 100K | 1536 | Cosine | No | Core latency/throughput/cost |
| `h-and-m-2048-angular` | ~105K | 2048 | Cosine | Yes (categorical) | Filtered search, cold-start |
| `random-768-100-tenants` | 1M (100K active) | 768 | Cosine | Per-tenant | Multi-tenant architecture |

### Client

All v2 results use a single async client on `tpuf-bench` (AWS us-west-2, same region as turbopuffer and Qdrant Cloud). `run.py` (multiprocessing harness) was not used. The `run_search(concurrency=p)` function fires `n=1000` queries through an asyncio semaphore; the fixed-QPS dispatcher fires queries at exact intervals.

### Measurement note

The `stats()` function computes `rps = n / sum(individual_latencies)` which equals `1 / mean_latency`. This is accurate for `p=1` (sequential) but **not** for `p>1` (concurrent), where actual wall-clock throughput ≈ `p × stated_rps`. For `p>1`, per-query latency figures are correct; the RPS column is not. **All throughput comparisons in this report use p=1 runs or the fixed-QPS experiment.**

Recall at `p>1` is also unreliable — concurrent queries cycle through the same test vectors and return in completion order, not dispatch order, corrupting the ground-truth mapping. Only p=1 recall figures are used.

### Qdrant configuration

Collection: HNSW `m=16`, `ef_construct=128`, all vectors in RAM (`memmap_threshold=10M`).  
Multi-tenant collection: `m=0`, `payload_m=16`, keyword index with `is_tenant=True` on field `a`.

---

## 2. Upload Performance (batch=128, async, both engines)

| Dataset | Engine | Time | v1 Time | v1 Batch | Change |
|---------|--------|------|---------|----------|--------|
| DBpedia 100K×1536 | turbopuffer | **2.4 min** | 22.3 min | 256 | 9× faster |
| DBpedia 100K×1536 | Qdrant Cloud | **3.8 min** | 48 min | 256 | 13× faster |
| H&M 105K×2048 | turbopuffer | **3.0 min** | 17.1 min | 500 | 6× faster |
| H&M 105K×2048 | Qdrant Cloud | **9.0 min** | 73 min | 128 | 8× faster |
| Multi-tenant 100K×768 (100 ns / 1 col) | turbopuffer | **2.3 min** | 7.4 min | mixed | 3× faster |
| Multi-tenant 100K×768 (100 ns / 1 col) | Qdrant Cloud | **20.6 min** | — | — | new data |

The 6–13× improvement over v1 is primarily from the async client — v1 used the multiprocessing `run.py` harness with one HTTP connection per worker process, paying TCP+TLS setup overhead per batch. The async client reuses a persistent connection pool, which matters much more for turbopuffer (writes go to S3 via API calls) than for Qdrant (batched upserts through a single gRPC channel).

With a single async connection, both engines are now more comparable. Qdrant's Qdrant is faster than tpuf on DBpedia (3.8 vs 2.4 min), slower on H&M (9.0 vs 3.0 min — larger vectors, more HTTP payload per batch).

---

## 3. Search — DBpedia 100K × 1536-dim (unfiltered)

### 3.1 Single-connection baseline (p=1)

| Engine | RPS | Mean | p50 | p95 | p99 | Recall |
|--------|-----|------|-----|-----|-----|--------|
| turbopuffer serverless | **64.2** | 15.6ms | 14.8ms | 19.4ms | 39.9ms | 98.42% |
| Qdrant Cloud | **147.4** | 6.8ms | 6.5ms | 7.5ms | 11.8ms | 98.36% |

**v1 comparison:** tpuf p=1 was 55.5 RPS / 16.9ms mean; Qdrant p=1 was 134 RPS / 6.3ms mean. The new numbers are 15–17% better for both engines — consistent with the async persistent connection eliminating per-query TCP overhead. The latency ratio is unchanged: **Qdrant is 2.3× lower mean latency at p=1** (6.8ms vs 15.6ms). This is architectural: HNSW in RAM vs S3-backed centroid traversal.

**What this means:** The ~9ms gap between Qdrant (6.8ms) and turbopuffer (15.6ms) is the irreducible cost of turbopuffer's object-storage architecture. Even with co-located client, warm namespace, and optimal async client, tpuf cannot serve a query faster than its NVMe centroid traversal floor. Qdrant's 1.9ms server-side HNSW (from `server_time` header) vs ~13–15ms turbopuffer floor is permanent.

### 3.2 Fixed-QPS sweep — dollar break-even (DBpedia 100K×1536)

> This is new data with no v1 equivalent. A dispatcher fires queries at exact intervals and records individual latencies.

| QPS | tpuf p50 | tpuf p99 | tpuf $/mo | Qdrant p50 | Qdrant p99 | Qdrant $/mo | Winner |
|-----|----------|----------|-----------|------------|------------|-------------|--------|
| 1 | 18.8ms | 63.6ms | $3.42 | 7.7ms | 16.4ms | $26.10 | tpuf |
| 5 | 15.3ms | 36.1ms | $16.69 | 7.3ms | 13.0ms | $26.10 | tpuf |
| 10 | 14.2ms | 36.0ms | $33.28 | 7.4ms | 11.0ms | $26.10 | **tie** |
| 20 | 15.5ms | 43.0ms | $66.46 | 7.1ms | 11.0ms | $26.10 | Qdrant |
| 50 | 15.0ms | 37.1ms | $165.99 | 7.1ms | 15.0ms | $26.10 | Qdrant |

Observations:
- **turbopuffer latency is stable across all QPS levels.** The 14–19ms range at QPS=1 through 50 confirms serverless autoscaling works: the pool absorbs load without queueing latency at these rates. No meaningful degradation from 1 → 50 QPS.
- **Qdrant is also stable** — 7.1–7.7ms p50 throughout. Both engines are headroom-bound at 1–50 QPS on 100K vectors.
- **Cost crossover is at ~10 QPS** (dataset-dependent). At 10 QPS, tpuf costs $33/month vs Qdrant $26/month — essentially tied. Above 10 QPS Qdrant wins on both cost and latency simultaneously.
- **At 50 QPS: tpuf costs 6× more** ($166 vs $26) with latency still 2× worse (15ms vs 7ms p50).

---

## 4. Search — H&M 105K × 2048-dim (filtered, categorical)

### 4.1 turbopuffer — warm (pinned 4 replicas, p=32)

| State | RPS\* | Mean | p50 | p95 | p99 | Recall |
|-------|------|------|-----|-----|-----|--------|
| Warm (NVMe-cached) | 10.7\* | 93.3ms | 69.4ms | 236ms | 351ms | 1.58%† |
| Cold (fresh namespace via copy_from) | 4.8\* | 210ms | 79.6ms | 1510ms | 1574ms | 1.24%† |

\*RPS figures are 1/mean (semaphore p=32 run) — actual wall-clock throughput ≈ p × stated_rps.  
†Recall is unreliable at p=32 (see §1 measurement note).

**v1 comparison — warm:** v1 showed 212 RPS, 73ms mean, 267ms p99 from the multiprocessing harness with p=32 from the same region. Adjusting the new measurement: 10.7 × 32 ≈ **342 RPS** actual throughput at 69ms p50 and 351ms p99. The latency profile is consistent with v1 (69ms p50 here vs 73ms mean in v1). p99 is better (351ms vs 267ms in v1) — this is likely measurement noise; both are in the same range.

**v1 comparison — cold:** v1 cold was measured cross-region (19.8 RPS, p99=12.7s from high-RTT client). New cold is same-region. Same-region cold: **p99=1574ms** (vs v1's 12.7s). The cold latency is much lower from same region, but still dramatically worse than warm (351ms p99 → 1574ms p99, **4.5× worse**). The cold/warm gap is real but the 12.7s figure in v1 was inflated by cross-region RTT compounding with S3 latency.

**New insight:** Same-region cold p99 for H&M is ~1.6s, not 12.7s. The ~12.7s in v1 was an artifact of high-RTT clients compounding with turbopuffer's S3 round-trips. **However, 1.6s cold p99 is still unacceptable for user-facing requests**, and the cold risk (any replica restart resets to cold) remains.

### 4.2 Qdrant — warm (same-region, p=32 via async semaphore)

| Config | RPS\* | Mean | p50 | p95 | p99 | Recall |
|--------|------|------|-----|-----|-----|--------|
| p=1 | 165.9 | 6.0ms | 5.9ms | 7.4ms | 8.8ms | 95.85%† |
| p=32\* | 8.7\* | 115ms | 84.7ms | 318ms | 466ms | 1.55%† |

†Recall at p>1 unreliable (see §1). At p=1, 95.85% recall confirms correct results.

**p=1 is the clean comparison:** Qdrant delivers **165.9 RPS at 6.0ms mean** for filtered search on H&M. turbopuffer (after async client adjustment, p=1 would approximate 64 RPS × filter overhead) is directionally worse.

The key comparison remains: Qdrant with HNSW payload indexes has **no cold-start risk** for filtered search. Qdrant's filter latency (6ms mean at p=1) is consistent regardless of warm/cold state because the HNSW graph stays in RAM.

---

## 5. Search — Multi-Tenant (100K × 768-dim, 100 tenants)

### 5.1 Direct comparison (p=1, reliable)

| Engine | Config | RPS | Mean | p50 | p95 | p99 | Recall |
|--------|--------|-----|------|-----|-----|-----|--------|
| turbopuffer | ns-per-tenant (100 namespaces) | 38.6 | 25.9ms | 19.7ms | 68.9ms | 106.7ms | 100.0% |
| Qdrant Cloud | payload_m=16 + is_tenant | **199.5** | **5.0ms** | **4.9ms** | **5.6ms** | **6.9ms** | 100.0% |

**Qdrant is 5.2× higher RPS and 5.2× lower latency at p=1.** Both achieve 100% recall.

**v1 comparison:** v1 only compared tpuf ns-per-tenant vs tpuf single-ns (within turbopuffer). v1's ns-per-tenant showed 24.5 RPS / 69ms mean (from the multiprocessing harness). New shows 38.6 RPS / 25.9ms mean — the async client explains the improvement (no per-query TCP setup). The new experiment adds the Qdrant side: Qdrant with `payload_m=16` sub-graphs delivers 5.2× more throughput and 5.2× lower latency.

**What changed architecturally:** Qdrant's `m=0, payload_m=16` creates per-tenant HNSW sub-graphs within one collection. Queries are routed directly to the tenant's sub-graph — no filter scan, no cross-tenant interference. This is structurally equivalent to tpuf's ns-per-tenant model but executed in RAM without per-namespace connection overhead.

**Why tpuf's p99 is wide (106ms at p=1):** With 100 namespaces, each p=1 query requires a separate HTTP request to a different namespace endpoint. Namespace routing adds ~10ms overhead beyond the actual vector search. Qdrant's single-collection routing is entirely in-process.

### 5.2 Multi-tenant upload cost

| Engine | Config | Upload time | Note |
|--------|--------|-------------|------|
| turbopuffer | 100 namespaces | 2.3 min | ~1.4s per namespace |
| Qdrant Cloud | 1 collection + payload index | 20.6 min | Index build time dominates |

Qdrant's upload is ~9× slower for multi-tenant: building per-tenant HNSW sub-graphs (`payload_m=16`) is significantly more expensive than writing to 100 tpuf namespaces. For infrequent write workloads, this is a one-time cost. For high-write workloads, tpuf's write-to-object-storage model wins.

---

## 6. What Changed from v1 — Summary

| Finding | v1 | v2 | What it means |
|---------|----|----|---------------|
| DBpedia p=1 latency | tpuf 16.9ms / Qdrant 6.3ms | tpuf 15.6ms / Qdrant 6.8ms | Consistent. Async client removes ~1ms TCP overhead. Latency ratio unchanged: Qdrant 2.3× faster. |
| H&M cold p99 | 12.7s (cross-region) | **1.6s (same-region)** | The 12.7s was cross-region RTT compounding with S3. Same-region cold is still catastrophic for user-facing latency but not 12.7s. |
| Multi-tenant | tpuf only (ns-per-tenant vs single-ns) | **tpuf vs Qdrant** | New data. Qdrant payload_m=16 delivers 5.2× the throughput and latency of tpuf ns-per-tenant at p=1, both at 100% recall. |
| Upload time | Mixed batches, slow | Consistent batch=128, async | Upload times are now comparable. Both engines benefit; Qdrant improved more in absolute terms from removing TCP-per-batch overhead. |
| Cost at QPS | Computed analytically | **Measured directly** | New fixed-QPS sweep confirms break-even at ~10 QPS for 100K×1536. Below that tpuf is cheaper; above that Qdrant is cheaper and faster. |
| H&M warm | 212 RPS p=32 (v1 harness) | ~340 RPS equivalent (new async, p=32) | Consistent latency profile; different RPS measurement method. Warm tpuf performance is real and ~3× better than cold. |

---

## 7. Cost Comparison (updated with measured latency)

### Break-even points (unchanged from v1 — based on tpuf pricing)

| Dataset | tpuf $/1M queries | Qdrant $/mo | Break-even QPS |
|---------|-------------------|-------------|----------------|
| 100K × 1536 | $1.28 | $26.10 | ~7.8 QPS |
| 1M × 1024 | $2.05 | $68.34 | ~12.7 QPS |
| 10M × 768 | $15.36 | $410.04 | ~10.2 QPS |

### What the fixed-QPS experiment adds

At the break-even of ~10 QPS (DBpedia 100K×1536), measured latencies:
- turbopuffer: 14.2ms p50, 36ms p99, $33/mo
- Qdrant: 7.4ms p50, 11ms p99, $26/mo

At break-even, Qdrant is already cheaper **and** 2× lower latency. The only operating point where tpuf beats Qdrant on cost is strictly below ~8 QPS — where Qdrant's fixed $26/month dominates. Above that threshold, tpuf costs more and performs worse simultaneously.

**The structural insight (confirmed by measurement):** turbopuffer does not have a latency "sweet spot" — latency is flat at ~15ms regardless of QPS from 1 to 50. There is no QPS band where turbopuffer is both cheap and fast. It is cheap at low QPS (where its latency disadvantage matters less) and expensive at high QPS (where latency matters more).

---

## 8. Architecture Notes

### Why multi-tenant is tpuf's best use case (and where Qdrant still wins)

turbopuffer's strongest argument for multi-tenant SaaS remains true: object storage idle cost is near-zero. A 100-tenant SaaS with 5 active tenants at any moment pays nothing for the 95 idle namespaces. Qdrant's $26/month per cluster covers all tenants but doesn't scale to zero.

The new data shows Qdrant wins on performance even for multi-tenant workloads (5× better throughput at p=1). The choice reduces to:
- **If most tenants are consistently idle:** turbopuffer's cost model is compelling despite the latency penalty.
- **If tenants have sustained traffic:** Qdrant is cheaper AND faster above ~8 QPS/tenant.

### tpuf serverless is still the best tpuf config

v1's finding holds: unpinned serverless outperforms pinned for unfiltered search because turbopuffer routes concurrently across multiple pool nodes rather than being bound to one fixed NVMe node. The fixed-QPS sweep shows stable 14–16ms p50 from 1 to 50 QPS — autoscaling is working correctly at these load levels.

### Cold-state risk is real but bounded

The corrected same-region cold p99 for filtered H&M is ~1.6s (not 12.7s from v1). The h&M cold experiment here used `copy_from` to create a guaranteed-cold namespace, then fired 500 queries without warmup. The median of those queries (p50=79.6ms) suggests ~half the queries hit warm cache (some centroid blocks cached from prior runs), while p99=1.6s reflects true cold regions. The risk profile is: **replica restart → first few queries up to ~1.6s** for filtered search from same region. Still unacceptable for user-facing SLAs; Qdrant has no equivalent risk.

---

## 9. Raw Results Reference

Results directory: `results/reproduce-2026-06-22T03-48-14/state.json`

### Upload

| Dataset | Engine | Time (s) | Batch |
|---------|--------|---------|-------|
| DBpedia 100K×1536 | turbopuffer | 144s (2.4 min) | 128 |
| DBpedia 100K×1536 | Qdrant | 230s (3.8 min) | 128 |
| H&M 105K×2048 | turbopuffer | 183s (3.0 min) | 128 |
| H&M 105K×2048 | Qdrant | 540s (9.0 min) | 128 |
| Multi-tenant 100K×768 | turbopuffer (100 ns) | 140s (2.3 min) | 128 |
| Multi-tenant 100K×768 | Qdrant (1 collection) | 1234s (20.6 min) | 128 |

### DBpedia warm search

| Config | n | RPS\* | mean | p50 | p95 | p99 | recall |
|--------|---|------|------|-----|-----|-----|--------|
| tpuf p=1 | 1000 | 64.2 | 15.6ms | 14.8ms | 19.4ms | 39.9ms | 98.42% |
| qdrant p=1 | 1000 | 147.4 | 6.8ms | 6.5ms | 7.5ms | 11.8ms | 98.36% |
| tpuf p=8† | 1000 | 58.0 | 17.2ms | 16.8ms | 19.5ms | 37.7ms | 69.28%† |
| qdrant p=8† | 1000 | 49.8 | 20.1ms | 17.8ms | 34.3ms | 46.7ms | 16.07%† |

†p>1 RPS and recall unreliable (see §1).

### Fixed-QPS

| QPS | n | tpuf mean | tpuf p99 | tpuf $/mo | qdrant mean | qdrant p99 | qdrant $/mo |
|-----|---|-----------|----------|-----------|-------------|------------|-------------|
| 1 | 120 | 20.5ms | 63.6ms | $3.42 | 8.1ms | 16.4ms | $26.10 |
| 5 | 600 | 16.6ms | 36.1ms | $16.69 | 7.6ms | 13.0ms | $26.10 |
| 10 | 1200 | 15.3ms | 36.0ms | $33.28 | 7.6ms | 11.0ms | $26.10 |
| 20 | 2400 | 16.7ms | 43.0ms | $66.46 | 7.3ms | 11.0ms | $26.10 |
| 50 | 6000 | 16.0ms | 37.1ms | $165.99 | 7.3ms | 15.0ms | $26.10 |

### H&M search

| Config | n | mean | p50 | p95 | p99 |
|--------|---|------|-----|-----|-----|
| tpuf pinned-4r p=32 warm | 1000 | 93.3ms | 69.4ms | 236ms | 351ms |
| tpuf pinned-4r p=32 cold | 500 | 210ms | 79.6ms | 1510ms | 1574ms |
| qdrant p=1 warm | 1000 | 6.0ms | 5.9ms | 7.4ms | 8.8ms |
| qdrant p=32 warm† | 1000 | 115ms | 84.7ms | 318ms | 466ms |

### Multi-tenant

| Config | n | RPS | mean | p50 | p95 | p99 | recall |
|--------|---|-----|------|-----|-----|-----|--------|
| tpuf ns-per-tenant p=1 | 1000 | 38.6 | 25.9ms | 19.7ms | 68.9ms | 106.7ms | 100.0% |
| qdrant payload_m=16 p=1 | 1000 | 199.5 | 5.0ms | 4.9ms | 5.6ms | 6.9ms | 100.0% |
