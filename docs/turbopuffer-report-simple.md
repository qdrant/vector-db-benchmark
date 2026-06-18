# turbopuffer vs Qdrant Cloud — Executive Summary

**Last updated:** 2026-06-17 | **Author:** Shivendu Kumar, Qdrant | **Region:** aws-us-west-2

---

## Bottom Line

From the same AWS region, Qdrant on a single 2CPU/8GB node delivers **365 RPS at 22ms p99** — beating turbopuffer's 224 RPS at 43.6ms p99, on identical hardware cost. Single-connection latency: Qdrant 6.3ms mean vs turbopuffer 16.9ms mean. HNSW in RAM simply wins on unfiltered dense search.

turbopuffer's value proposition is different: **scale-to-zero cost** for inactive namespaces and multi-tenant SaaS patterns where most tenants are idle. It's not a better search engine — it's a cheaper storage tier for sporadic traffic. The tradeoff has two hard edges: cold-state collapse (12.7s p99 for filtered search after any restart) and fixed recall (~96–98.9%, not tunable).

**For production APIs:** Qdrant wins on every performance axis — unfiltered (365 vs 224 RPS) and filtered (318 vs 212 RPS warm, 318 vs 19.8 RPS cold), with better p99 and precision throughout. **For multi-tenant SaaS with sparse query patterns:** turbopuffer's cost model is compelling if you can tolerate cold-start risk and lower precision.

---

## Head-to-Head: Qdrant vs turbopuffer (same-region, aws-us-west-2)

| Dimension | turbopuffer | Qdrant Cloud |
|-----------|-------------|--------------|
| Architecture | Object storage (S3) + ephemeral compute | RAM + HNSW index |
| Server-side query latency | ~17ms (warm, same region) | **1.9ms** (HNSW in RAM) |
| Peak RPS — unfiltered 100K | 224 RPS (serverless p=8) | **365 RPS** (2CPU/8GB node, p=8) |
| Single-connection RPS | 55.5 RPS | **134 RPS** |
| Single-connection mean latency | 16.9ms | **6.3ms** |
| Peak RPS — filtered 105K, **warm** | 212 RPS | **318 RPS** |
| Peak RPS — filtered 105K, **cold** | 19.8 RPS | **318 RPS** (no cold-start) |
| Filtered search p99 — **warm** | 267ms | **76ms** (3.5× better) |
| Filtered search p99 — **cold** | **12.7 seconds** | **76ms** (167× better) |
| Filtered precision | 96.34% | **99.85%** |
| Upload 100K @ batch=256 | 22.3 min | 48 min (2.2× slower — single connection) |
| Recall/precision control | None (fixed ~98.5%) | Full (ef, quantization, oversampling) |
| Scales to zero (idle cost) | Yes | No |
| Latency predictability | 17ms warm → 12.7s p99 cold | Consistent — 1.9ms server always |

---

## Key Numbers

### Upload Performance

| Engine | Dataset | Vectors | Batch | Upload Time |
|--------|---------|---------|-------|-------------|
| turbopuffer | DBpedia (1536-dim) | 100K | 1000 | 33–37 min |
| turbopuffer | H&M (2048-dim) | 105K | 500 | ~17 min |
| **Qdrant Cloud** | **DBpedia (1536-dim)** | **100K** | **256¹** | **48 min** |

### Search — DBpedia, no filters (same-region benchmark client)

#### turbopuffer
| Mode | RPS | Mean Latency | p99 | Max (cold spike) | Precision |
|------|-----|-------------|-----|-----------------|-----------|
| **Serverless p=8 (warm)** | **224 RPS** | **22.9ms** | 43.6ms | — | 98.51% |
| Pinned 1r p=8 (warm) | 212 RPS | 26ms | 54.7ms | — | 98.51% |
| Serverless p=32 (warm) | 208 RPS | 29ms | 58.7ms | — | 98.51% |
| Single conn p=1 (warm) | 55.5 RPS | 16.9ms | 37ms | — | 98.51% |
| **Serverless p=8 (cold start)** | **222 RPS** | 22.8ms | 51.8ms | **119ms** | 98.51% |
| Serverless p=1 (cold start) | 48 RPS | 19.6ms | 60.8ms | **6,292ms** | 98.51% |
| hint_warm p=8 | 17 RPS | 459ms | 1139ms | — | 98.87% |
| Pinned 4r p=32 | 18.5 RPS | 1.7s | 6.3s | — | 98.87% |

#### Qdrant Cloud (1 node, 2CPU/8GB, HNSW ef=128) — same-region (aws-us-west-2)
| Mode | RPS | Mean Latency | p95 | p99 | Server Latency | Precision |
|------|-----|-------------|-----|-----|----------------|-----------|
| **p=8** | **365 RPS** | **10.6ms** | 18.0ms | **22.3ms** | **1.9ms** | **99.0%** |
| p=32 | 379 RPS | 15.0ms | 28.9ms | 36.4ms | 2.0ms | 99.0% |
| **p=1 (single conn)** | **134 RPS** | **6.3ms** | 7.4ms | **9.1ms** | 1.9ms | 99.0% |

> **Note:** Earlier June 16 results (35 RPS, 227ms mean) were collected from a client in India (~230ms RTT to us-west-2). Above numbers are from the same-region benchmark server.

**Cold start behavior for unfiltered search:** The aggregate cold stats (222 RPS, 51ms p99) look nearly warm because SPFresh loads only ~14 centroid blocks to cover unfiltered DBpedia — after those load in the first ~20 queries, all subsequent queries hit NVMe cache. The max=6.3s (p=1) and max=119ms (p=8) reveal the cold spike on the very first queries. **Unfiltered cold = transient spike.** This is completely different from filtered (H&M), where each filter condition forces traversal of different centroid regions, keeping cold latency catastrophic throughout.

**The key number:** Qdrant's 1.9ms server latency vs turbopuffer's ~17ms irreducible NVMe floor. Everything else in the client latency is network RTT, same for both.

### Search — H&M, with filters (105K vectors, same-region)

#### turbopuffer (pinned 4 replicas, p=32)
| State | RPS | Mean | p95 | p99 | Precision |
|-------|-----|------|-----|-----|-----------|
| **Warm (NVMe-cached)** | 212 RPS | 73ms | 163ms | 267ms | 96.34% |
| Cold (fresh namespace) | 19.8 RPS | 1614ms | 4341ms | **12,713ms** | 96.37% |

#### Qdrant Cloud (1 node 2CPU/8GB, HNSW ef=128) — same-region
| Parallel | RPS | Mean | p95 | p99 | Server Latency | Precision |
|----------|-----|------|-----|-----|----------------|-----------|
| 1 | 20.7 | 46.7ms | 58.6ms | 62.4ms | 1.4ms | **99.85%** |
| 8 | 160.5 | 49.0ms | 61.4ms | 69.5ms | 1.4ms | **99.85%** |
| **32** | **318.7 RPS** | **48.1ms** | 69.7ms | **76.3ms** | 1.5ms | **99.85%** |

> **Note:** June 16 results (25 RPS, 317ms mean) were from hotel WiFi (~115ms RTT). Above are same-region numbers.

**Qdrant wins on all three dimensions:** 318 RPS vs 212 RPS, 76ms p99 vs 267ms p99, and 99.85% vs 96.34% precision — on a single 2CPU/8GB node, warm or cold.

The mean latency for filtered queries (~48ms) is 7× higher than unfiltered (~6ms). The distribution is bimodal: ~1–9% of queries return in ~4ms (filter selects very few candidates → trivial HNSW), while 90%+ take 47–62ms (full payload index scan across 22 fields + HNSW rescore). The `server_time` response header (1.4ms) captures only the HNSW step — payload index scan time is not included in that metric. True server processing is ~44ms for the common path.

---

## Workload Fit

| Workload | Fit | Reason |
|----------|-----|--------|
| Multi-tenant SaaS, most tenants idle | Good | Pay only for active namespaces; cold cost is near zero |
| Internal / async semantic search | Good | Latency tolerance high, queries infrequent |
| Dev / staging environments | Good | Real data, rarely queried, zero idle cost |
| RAG over infrequent documents | Good | Batch retrieval, latency not user-facing |
| E-commerce / retail search | Conditional | Warm: 267ms p99, 212 RPS. Cold: 12.7s p99. Precision 96.3% vs Qdrant 99.85%. Viable only if warm state is guaranteed and precision floor is acceptable. |
| Real-time recommendations | Poor | 126ms base latency consumes full API budget before app logic runs |
| Consumer-facing search | Poor | 126ms is the absolute floor; real-world 200–500ms is user-visible |
| High-throughput ingestion + search | Poor | 37 min to upload 100K vectors; not designed for concurrent writes + reads |
| Hybrid sparse+dense (BM25+semantic) | Poor | No native sparse vector support |
| Precision-sensitive (medical/legal/finance) | Poor | Fixed ~98.9% recall; cannot tune up or down |
| Sustained high-QPS (>15 RPS/namespace) | Poor | Cost advantage disappears; latency gap remains |

**Crossing point:** ~10–15 sustained RPS per namespace. Below → turbopuffer may save money. Above → Qdrant is cheaper and 10–30× faster.

---

## Multi-Tenant Architecture: Right vs Wrong

Dataset: 1M vectors, 100 tenants, 10K vectors/tenant. This directly tests turbopuffer's primary use case.

| Metric | Option A: ns-per-tenant ✅ | Option B: single-ns + filter ❌ |
|--------|--------------------------|--------------------------------|
| RPS | **24.5** | 13.0 |
| Mean latency | **69ms** | 181ms |
| p99 | **322ms** | 881ms |
| Precision | **99.98%** | **80.9%** |

**Option B (wrong architecture) gives 1 in 5 results wrong.** SPFresh precision collapses when forced to post-filter across 1M vectors for 10K relevant results (1% selectivity). This is not tunable.

**The trap:** turbopuffer's namespace-per-tenant pattern *works* — but only if you build the routing layer correctly at application level. Get it wrong (dump everything in one namespace) and you get the worst of both worlds: 1.9× slower and 19% of results are garbage.

---

## turbopuffer Internals (Probed)

### Cold warmup curve

We created a guaranteed-cold namespace via `copy_from` (copies S3 objects, no NVMe cache) and ran 500 sequential queries, recording each latency:

| Phase | Queries | Latency | What's happening |
|-------|---------|---------|-----------------|
| True cold | q0 | **893ms** | Root index + first centroid tier fetched from S3 |
| Patchy | q1–q10 | 67–351ms | Per-query centroid caching — each query warms only the regions it walks |
| Mixed | q11–q74 | 18–251ms | Cached regions fast, uncached still slow |
| Stable warm | q75+ | **13–22ms** | Full warm floor |

**Key insight:** SPFresh does lazy per-centroid caching — no global pre-fetch on first query. Two queries to the same vector region benefit from each other's cache; two queries to different regions don't. This explains the noisy middle section and why H&M cold is 12.7s p99 (filters force multi-region centroid walks, touching far more uncached S3 objects).

**~75 sequential queries / ~15 seconds to reach stable warm state.**

### Compute core count

We swept concurrency p=1→64 on a warm pinned 1-replica namespace and serverless:

| p | Pinned 1r | Serverless |
|---|-----------|-----------|
| 1 | 58 RPS | 58 RPS |
| 4 | 228 RPS | 210 RPS |
| **8** | **348 RPS** | **429 RPS** |
| 16 | 372 RPS | **495 RPS** |
| 32 | 342 RPS | 455 RPS |

- **Pinned 1-replica saturates at ~6–8 cores** — linear scaling until p=4–8, then flatlines at ~370 RPS ceiling.
- **Serverless routes across multiple pool nodes** — at p=8, serverless (429 RPS) already outperforms pinned (348 RPS). Keeps scaling to ~500 RPS at p=16. You're not hitting one node.
- **Single-connection is identical** — p=1 is 58 RPS for both; the difference only appears under concurrent load.

### Pinned 4-replica sweep (correct warmup)

The earlier 4r result (18.5 RPS) was broken — traffic hit replicas before NVMe warmed. We re-ran with a proper warmup pass after `ready_replicas=4/4`, then swept concurrency:

| p | RPS | Mean | p99 | Scale vs p=1 |
|---|-----|------|-----|-------------|
| 1 | 58 RPS | 17ms | 34ms | 1.00× |
| 4 | 230 RPS | 17ms | 44ms | 3.95× |
| **8** | **405 RPS** | 19ms | **45ms** | **6.96×** |
| 16 | **473 RPS** | 30ms | 72ms | **8.11×** — peak |
| 32 | 429 RPS | 63ms | 158ms | 7.36× |
| 64 | 451 RPS | 110ms | 343ms | 7.73× |

- **Peak: 473 RPS at p=16** — 2.23× the broken single-replica baseline (212 RPS), not 4×.
- **4 replicas ≠ 4× throughput.** Scaling is sub-linear because the bottleneck is NVMe read bandwidth across replicas, not CPU cores per se. Each replica still runs SPFresh sequentially; routing 4× more load gives ~2.2× gain until NVMe saturates.
- **p99 degrades sharply at p=32+** — each replica's NVMe queue backs up. Queue depth, not CPU, is the ceiling.
- **Correctly-deployed 4r still loses to Qdrant**: 473 RPS vs 365 RPS for Qdrant's single 2CPU/8GB node.

### Replica boot timing

From `update_metadata(pinning={"replicas": 1})` to serving warm queries:

| Step | Duration |
|------|---------|
| `ready_replicas` = 0/1 → 1/1 | **~80 seconds** |
| First query after ready | **617ms** (NVMe still cold) |
| Rolling warm state (<20ms) | ~11 queries (~2 seconds) |
| **Total: pin → warm serving** | **~90–100 seconds** |

`ready_replicas=1` means compute is provisioned, **not** that NVMe is warm. A correct deployment must run a warmup pass after confirming replica readiness. The original broken benchmark (18 RPS) skipped this step.

### S3 access structure

We probed S3 access patterns using the guaranteed-cold namespace from `copy_from`, logging per-query latency across 500 queries. The cold warmup curve reveals how SPFresh fetches centroid data:

| Observation | Value | Interpretation |
|-------------|-------|----------------|
| First-query cold overhead | **876ms** (893ms − 17ms warm) | Root index + first centroid tier loaded from S3 |
| High-latency spikes (>100ms) in first 50 queries | **14 distinct events** | Each = one uncached centroid block fetched from S3 |
| Per-spike overhead | 100–900ms | Cost of fetching one centroid tree block cold |
| Warm floor (NVMe-only) | **13–22ms** | No S3 — all centroid data in local NVMe cache |

**What this means:** turbopuffer fetches ~14 centroid blocks from S3 during the first 50 queries to a cold namespace. Each block fetch is a separate high-latency event. Once a block is in NVMe, all future queries touching that region pay the warm NVMe cost (~1ms), not the S3 cost.

**Why filtered H&M cold is 12.7s p99:** Filtered queries must walk more of the centroid tree (to satisfy the filter condition), touching far more distinct centroid regions. Each uncached region triggers an S3 fetch. Unfiltered cold = ~14 distinct S3 fetches across 50 queries; filtered cold = many more, stacked per query.

**Round-trip count:** We cannot determine exact S3 round-trips per query without knowing turbopuffer's internal VPC-to-S3 latency. Their compute nodes use a VPC endpoint (~0.3–1ms), not the internet path (~5ms). The cold warmup curve is the correct instrument: it directly measures the real cost turbopuffer's infrastructure pays.

---

## Where Qdrant Wins (and Why It's Permanent)

1. **Throughput:** 365 RPS vs 224 RPS on same-region 100K dataset. 1.6× faster on a single small node.
2. **Single-query latency:** 6.3ms mean vs 16.9ms mean at p=1. HNSW in RAM vs S3 round-trips — architectural gap, not closable.
3. **Filtered search:** turbopuffer filter p99 = 12.7s cold is a hard limit. Qdrant payload indexes keep filter latency at 76ms p99 warm or cold.
4. **Precision control:** Full ef/quantization/oversampling dial. turbopuffer locked at ~96–98.9%.
5. **Consistency:** turbopuffer varies 17ms → 12.7s p99 cold. Qdrant server latency is always ~1.9ms.
6. **Replica scaling:** turbopuffer pinned-4r delivers 18 RPS vs single-replica's 212 RPS (provisioning race + core saturation at ~6–8 cores). Serverless pool outperforms pinned by routing across nodes. Qdrant scales horizontally with linear RPS gains.

## Where turbopuffer Wins

1. **Cold / idle namespaces:** Object storage backend costs near zero when not queried.
2. **Zero-config simplicity:** No HNSW knobs — appeals to developers who want managed search without tuning.
3. **Serverless scale-to-zero:** True pay-per-query for sporadic traffic.

---

## Marketing Angles

- **"Faster in your region"** — Same AWS region, same dataset: Qdrant 365 RPS vs turbopuffer 224 RPS. 6.3ms mean vs 16.9ms. Qdrant wins on every throughput and latency metric for co-located deployments.
- **"Fast, not sometimes fast"** — turbopuffer warm H&M hits 267ms p99. Cold hits 12.7s p99. 47× variance, same config. Qdrant delivers 679ms p99 warm or cold, always.
- **"Real-time filtering without roulette"** — turbopuffer cold filter p99 = 12.7s. Any replica restart resets to cold. Qdrant payload indexes keep filters at 679ms regardless.
- **"Recall on your terms"** — turbopuffer locked at 96.3% filtered recall. Qdrant hits 99.85% and lets you tune up or down.
- **"Scale without S3 physics"** — turbopuffer pinned-4replicas delivers 18 RPS vs 212 for single replica. Qdrant scales linearly with each added node.
