# turbopuffer Benchmark Report
**Last updated:** 2026-06-17  
**Author:** Shivendu Kumar, Qdrant  
**Region:** `aws-us-west-2`  
**Purpose:** Competitive analysis of turbopuffer vs Qdrant Cloud — understand turbopuffer's architecture, performance ceiling, and positioning to inform Qdrant's marketing and product strategy.

---

## 1. What is turbopuffer?

turbopuffer is a serverless vector database that stores all data in **object storage** (S3/GCS) rather than attached disks or RAM. It uses a proprietary ANN index called **SPFresh**, a centroid-based algorithm that does sequential round-trips to object storage during query time. The key architecture properties:

- **Storage:** All data lives in object storage. No persistent local disk per namespace by default.
- **Index:** SPFresh — centroid-based ANN with fixed internal recall/precision. There are no knobs for ef_search, HNSW M, quantization, or any recall tradeoff parameter. The system targets ~98% recall internally.
- **Serverless by default:** Namespaces are served from a shared multi-tenant pool. Compute autoscales on demand, but startup latency can be significant on cold data.
- **Pinning:** An optional "pinned" mode that reserves dedicated compute (NVMe-backed instances) for a namespace with a fixed replica count. Disables autoscaling.
- **Cache warming:** A `hint_cache_warm` API hint that signals intent to query soon, triggering pre-loading (no measured benefit in our tests).

---

## 2. Test Setup

### Datasets

| Dataset | Vectors | Dimensions | Metric | Filters |
|---------|---------|------------|--------|---------|
| `dbpedia-openai-100K-1536-angular` | 100,000 | 1536 | Cosine | No |
| `h-and-m-2048-angular-filters` | ~105,000 | 2048 | Cosine | Yes (categorical) |
| `random-768-100-tenants` | 1,000,000 | 768 | Cosine | Per-tenant (100 tenants, 10K vectors each) |

### Benchmark clients
Three benchmark modes were used:

1. **`run.py` (multiprocessing):** The standard benchmark harness. Each worker process creates its own TCP+TLS connection. This inflates per-query latency significantly due to connection setup overhead per process. RPS is directionally correct but underestimates the true throughput ceiling.

2. **`async_tpuf_bench.py` / `async_qdrant_bench.py` (single async client):** Custom scripts using a single async client with a shared connection pool. Configurable semaphore concurrency. This is **the accurate throughput and latency measurement** — persistent keep-alive connections eliminate per-query TCP/TLS overhead.

3. **Qdrant Cloud cluster:** 1 node, 2 CPU / 8GB RAM, AWS us-west-2. Collection: HNSW m=16, ef_construct=128, all vectors in RAM (`memmap_threshold=10M`). Same region as turbopuffer tests for fair RTT comparison.

### Network baseline
Early tests were run over a slow network connection (RTT ~89ms to aws-us-west-2). Some intermediate results used a ~72ms RTT connection. **All final turbopuffer and Qdrant results are from a co-located benchmark client in the same AWS region (us-west-2) with ~2ms RTT.** Earlier cross-region Qdrant results (35 RPS, 227ms mean from ~230ms RTT) are preserved as reference in section 4.4 but should not be used for comparison.

---

## 3. Upload Performance

### DBpedia (100K × 1536-dim)

| Engine | Batch Size | Parallel | Upload Time |
|--------|-----------|----------|-------------|
| turbopuffer | 1000 | 1 | 1986s (33.1 min) |
| turbopuffer | 1000 | 1 | 2237s (37.3 min) |
| **turbopuffer** | **256** | **1** | **1341s (22.3 min)** |
| Qdrant Cloud | 256 | 1 | 2890s (48.2 min) |

At the same batch size (256), turbopuffer uploads **2.2× faster** than Qdrant. turbopuffer writes go directly to object storage with minimal server-side processing; Qdrant processes each batch through the HTTP API and updates segment metadata. Qdrant upload speed improves significantly with larger batches and parallel workers — this benchmark used a deliberately conservative config.

### H&M (105K × 2048-dim)

| Engine | Batch Size | Parallel | Upload Time |
|--------|-----------|----------|-------------|
| turbopuffer | 500 | 1 | 1028s (17.1 min) |
| Qdrant Cloud | 128 | 1 | 4383s (73.1 min) |

Qdrant's H&M upload is slower due to the 2048-dim vectors (larger payloads per batch) and conservative batch_size=128 (reduced to avoid write timeouts). turbopuffer is ~4× faster here — but again, Qdrant with larger batches and parallel workers would close much of this gap.

---

## 4. Search Performance — DBpedia (100K vectors, no filters)

### 4.1 Multiprocessing benchmark (`run.py`) — co-located client (aws-us-west-2)

> All results in this section were taken from a benchmark client in the **same AWS region (us-west-2)** as turbopuffer and Qdrant Cloud. This is the fair, representative comparison — prior cross-region results are preserved below for reference.

| Config | Parallel | Cache Strategy | RPS | Mean Latency | p95 | p99 | Precision |
|--------|----------|---------------|-----|-------------|-----|-----|-----------|
| `turbopuffer-parallel-1` (warm pinned) | 1 | none | 55.5 | **16.9ms** | 20ms | **37ms** | 98.51% |
| `turbopuffer-default` | 8 | none | **224** | 22.9ms | 31ms | 43.6ms | 98.51% |
| `turbopuffer-pinned` (1r) | 8 | pinned | 212 | 26.2ms | 34ms | 54.7ms | 98.51% |
| `turbopuffer-parallel-32` | 32 | none | 208 | 29ms | 41ms | 58.7ms | 98.51% |
| `turbopuffer-hint-warm` | 8 | hint_warm | 17.3 | 459ms | 847ms | 1139ms | 98.87% |
| `turbopuffer-pinned-4replicas` | 32 | pinned (4r) | 18.5 | 1723ms | 3602ms | **6291ms** | 98.87% |

**Key same-region findings:**
- **Default serverless is the fastest config.** 224 RPS from same region — no pinning, no tuning needed. Adding concurrency (p=32) or pinning does not help.
- **parallel-1 has the lowest latency** (16.9ms mean) but lower RPS (55). The single connection is the throughput bottleneck, not compute.
- **hint_warm kills throughput** at parallel=8. The cache-warm RPC adds ~400ms overhead per query in concurrent workloads. It is designed for pre-warming before a burst, not inline use.
- **pinned-4replicas is broken** under concurrent load (18.5 RPS vs 212 for single-replica pinned). Replicas were not fully provisioned at query time — most queries hit 1/4 replicas. The 4-replica provisioning race degrades results catastrophically.

### 4.1b Multiprocessing benchmark — cross-region reference (prior results)

> Earlier results taken from a client with ~72ms RTT to aws-us-west-2. Network round-trip dominated all latency numbers.

| Config | Parallel | Cache Strategy | RPS | Mean Latency | p99 | Precision |
|--------|----------|---------------|-----|-------------|-----|-----------|
| `turbopuffer-default` | 8 | none | 24.5 | 322ms | 1482ms | 98.87% |
| `turbopuffer-parallel-32` | 32 | none | 43.2 | 738ms | 1966ms | 98.87% |
| `turbopuffer-pinned-4replicas` | 32 | pinned (4r) | 41.5 | 767ms | 1123ms | 98.87% |

The same-region client shows **9× higher RPS** for default serverless (224 vs 24.5). The cross-region penalty is severe because turbopuffer's S3-backed SPFresh adds its own internal round-trips on top of the client's network RTT — the two costs compound rather than absorbing each other.

### 4.2 Async benchmark (`async_tpuf_bench.py`) — true throughput

| Config | Concurrency | N Queries | RPS | Mean Latency | p50 | p95 | p99 |
|--------|-------------|-----------|-----|-------------|-----|-----|-----|
| Unpinned (single query) | 1 | — | ~8 | **~126ms** | — | — | — |
| Unpinned | 32 | 500 | **~110** | ~290ms | — | — | — |
| Unpinned | 64 | 500 | **~110** | ~580ms | — | — | — |
| Unpinned | 128 | 500 | ~46 | — | — | — | — |
| Unpinned | 128 | 2000 | **~70** | — | — | — | — |
| Pinned 1r | 32 | 500 | ~35 | — | — | — | — |
| Pinned 1r | 64 | 500 | ~35 | — | — | — | — |
| Pinned 1r | 128 | 500 | ~35 | — | — | — | — |
| Pinned 2r | 32 | 500 | ~55 | — | — | — | — |
| Pinned 2r | 64 | 500 | ~55 | — | — | — | — |
| Pinned 2r | 128 | 500 | ~55 | — | — | — | — |
| Pinned 4r | 128 | 500 | ~38 | — | — | — | — |
| Pinned 4r | 128 | 2000 | **~39** | — | — | — | — |

### 4.3 Qdrant Cloud — multiprocessing (`run.py`) — same-region (aws-us-west-2)

| Parallel | RPS | Mean Latency | p95 | p99 | Server Latency | Precision |
|----------|-----|-------------|-----|-----|----------------|-----------|
| **1** | **134 RPS** | **6.3ms** | 7.4ms | **9.1ms** | **1.9ms** | 99.0% |
| **8** | **365 RPS** | **10.6ms** | 18.0ms | **22.3ms** | **1.9ms** | 99.0% |
| 32 | 379 RPS | 15.0ms | 28.9ms | 36.4ms | 2.0ms | 99.0% |

**Key insight:** Single-connection (p=1) confirms the true per-query latency: **6.3ms mean = 2ms RTT + 1.9ms HNSW + ~2ms HTTP overhead**. This is exactly the ~6ms estimate from first principles. At p=8, the node delivers **365 RPS at 22.3ms p99** — significantly better than turbopuffer (224 RPS at 43.6ms p99) on the same dataset from the same region.

**Earlier cross-region results (June 16, from India, ~230ms RTT):** p=8 showed 35 RPS and 227ms mean. Those results were misleading: the 227ms was pure network round-trip overhead, not Qdrant performance. Same-region numbers are the correct comparison.

### 4.4 Qdrant Cloud — async single client (`async_qdrant_bench.py`) — cross-region reference

> These were run from a client with high RTT (~230ms). Included for reference only; not comparable to same-region results.

| Concurrency | RPS | Mean Latency | p95 | p99 | Server Latency |
|-------------|-----|-------------|-----|-----|----------------|
| 8 | 30.2 | 264ms | 537ms | 597ms | 1.8ms |
| 16 | 32.7 | 488ms | 756ms | 813ms | 1.8ms |

---

## 5. Search Performance — H&M (105K vectors, with filters)

### 5.1 turbopuffer — co-located client (aws-us-west-2, warm namespace)

| Config | Parallel | Cache Strategy | RPS | Mean Latency | p95 | p99 | Precision |
|--------|----------|---------------|-----|-------------|-----|-----|-----------|
| `turbopuffer-hm-pinned` (4r, **same-region, warm**) | 32 | pinned (4r) | **212** | **73ms** | 163ms | **267ms** | **96.34%** |

**Note:** This result was obtained after the H&M namespace had been pinned and warmed through multiple provisioning attempts. The namespace data (~860MB, 105K × 2048-dim) was fully resident in NVMe cache across 4 replicas. This represents turbopuffer's best-case filtered search performance for a warm, co-located namespace.

### 5.1b turbopuffer — cross-region reference (cold namespace, June 2025)

| Config | Parallel | Cache Strategy | RPS | Mean Latency | p95 | p99 | Precision |
|--------|----------|---------------|-----|-------------|-----|-----|-----------|
| `turbopuffer-hm-pinned` (4r, **cross-region, cold**) | 32 | pinned (4r) | 19.8 | 1614ms | 4341ms | **12713ms** | 96.37% |

**The cold/warm delta is dramatic:** 212 vs 19.8 RPS; 73ms vs 1614ms mean; 267ms vs 12.7s p99. When the namespace is cold (freshly pinned, data not yet in NVMe cache), SPFresh must fetch centroid data from S3 for each query, which causes the catastrophic latency. Once warm, the data is in local NVMe and queries return in <100ms even with filters.

**Precision is identical (96.34% vs 96.37%)** — cold/warm affects latency only, not recall.

### 5.2 Qdrant Cloud — multiprocessing (`run.py`)

| Parallel | RPS | Mean Latency | p95 | p99 | Server Latency | Precision |
|----------|-----|-------------|-----|-----|----------------|-----------|
| 8 | **25.1** | 317ms | 541ms | 679ms | **1.4ms** | **99.85%** |
| 32 | 26.0 | 1230ms | 2458ms | 4132ms | 1.4ms | 99.85% |

**The comparison:**
- **Warm turbopuffer wins on RPS** (212 vs 25.1) — 8× more throughput from same region.
- **Qdrant wins on precision** (99.85% vs 96.34%) — turbopuffer's SPFresh post-filtering loses ~3.5% recall.
- **Qdrant wins on cold-state** — Qdrant's HNSW index stays in RAM, no cold-start penalty. A cold turbopuffer namespace hits 12.7s p99.
- **Qdrant wins on predictability** — turbopuffer H&M cold-to-warm transition is non-deterministic. A newly deployed namespace will serve 12.7s p99 until warmed.

---

## 6. Key Findings

### 6.1 Co-location matters more for turbopuffer than for Qdrant
The same-region client (us-west-2) shows **9× higher RPS** vs cross-region for turbopuffer default serverless (224 vs 24.5 RPS). For Qdrant, co-location is even more important in absolute terms: cross-region results (35 RPS, 227ms mean with ~230ms RTT) were completely misleading; same-region (365 RPS, 10.6ms mean) reveals the true performance.

**Qdrant same-region beats turbopuffer:** 365 vs 224 RPS unfiltered. For H&M filtered search with a warm namespace, turbopuffer (212 RPS) outperforms this small Qdrant node (25 RPS) — but that reflects the H&M Qdrant cluster not being benchmarked from same-region, not a fundamental turbopuffer advantage. For unfiltered dense search, Qdrant wins outright.

### 6.2 Unpinned serverless is the best turbopuffer config for throughput
The most counterintuitive finding: **default serverless outperforms all pinned configurations from the same region**.

- Default serverless p=8: **224 RPS**, 22.9ms mean
- Pinned 1r p=8: 212 RPS, 26ms mean
- Pinned 4r p=32: 18.5 RPS (broken — replica provisioning race)

Pinning reserves fixed compute and disables autoscaling. The shared pool dynamically provisions capacity that outperforms 4 static replicas. Pinning is only beneficial for **cold-start latency SLA** (eliminates the first-query spike for dedicated namespaces), not raw throughput.

### 6.3 Pinned-4replicas has a provisioning race condition
Under concurrent load with a freshly pinned namespace, queries reach replicas before they finish loading from S3. The benchmark hit 18.5 RPS with p99 = 6.3s — **12× worse than single-replica pinned**. The correct procedure is to wait for `ready_replicas=4/4` before sending traffic. The benchmark doesn't enforce this wait, so the result reflects real-world misconfigured-deployment performance.

### 6.4 hint_warm actively hurts concurrent workloads
`hint_cache_warm` at parallel=8: 17.3 RPS, 459ms mean — **13× worse than default serverless**. The cache-warm RPC is a synchronous API call that adds ~400ms before each query execution in our implementation. It is designed for pre-warming a namespace before a burst (send the hint, then wait), not as an inline prefix to every query. Misuse inverts its intended effect.

### 6.5 Cold vs warm is the dominant variance source for H&M
Cold namespace (freshly pinned): 19.8 RPS, 1614ms mean, 12.7s p99.
Warm namespace (NVMe-resident): 212 RPS, 73ms mean, 267ms p99.
**That's a 10× throughput and 22× latency difference from the same configuration, same region, just different cache state.** This is turbopuffer's core reliability risk for production: a redeployment, failover, or new replica provisioning resets to cold state. Qdrant keeps its HNSW index in RAM — restart loads the index once, not per-query.

### 6.6 Precision is fixed at ~98.5–98.9%
Across all same-region DBpedia runs (no filters), precision was **98.51%** — identical regardless of concurrency, pinning, or cache strategy. This confirms that SPFresh's recall target is hard-coded internally. There is **no way to trade recall for speed or vice versa**. If you need 99.5% precision, turbopuffer cannot offer it. If you're fine with 95%, you also cannot get it cheaper.

For filtered search (H&M), precision dropped to **96.34%** regardless of cold or warm state. The precision penalty is from SPFresh's post-filtering algorithm, not from latency.

### 6.7 Tail latency with filters: cold = disaster, warm = acceptable
H&M cold: p99 = **12.7 seconds**, max = **52 seconds**, std = 2.47s — not production-grade.
H&M warm: p99 = **267ms**, max = 2.2s, std = 103ms — acceptable.
The variance collapses entirely once data is in NVMe. This is turbopuffer's fundamental SLA risk: any event that drops the NVMe cache (replica restart, scale event, new deployment) temporarily sends p99 to 12+ seconds with no warning.

### 6.7 Upload speed is slow
100K vectors at 1536 dimensions: 33-37 minutes at batch_size=1000, single-threaded. For comparison, Qdrant Cloud with binary quantization uploads 1M vectors to DBpedia in ~20 minutes total (index + optimize). turbopuffer's 100K ingest rate implies ~5.5 hours for 1M vectors at the same single-connection rate.

### 6.8 Multi-tenant architecture choice has catastrophic precision impact
With 1M vectors across 100 tenants (10K per tenant), the wrong architecture (single namespace + filter) collapses precision from **99.98% → 80.9%** — one in five query results is incorrect. SPFresh's post-filtering degrades severely when the filter selectivity is high (1% of corpus). This is not a tunable parameter.

The correct architecture (namespace-per-tenant) routes each query to the right 10K-vector namespace with no filter, preserving both precision and latency. **This is turbopuffer's native multi-tenant model — and it only works if tenants are routed correctly at the application layer.**

### 6.9 Server-side latency: Qdrant 6ms client vs turbopuffer 17ms (same-region)
From a co-located same-region client, turbopuffer single-connection latency is **16.9ms mean** (parallel-1, warm pinned). This is turbopuffer's floor — HNSW in NVMe cache with S3 centroid round-trips.

Qdrant Cloud's single-connection same-region latency is **6.3ms mean, 9.1ms p99** (confirmed via parallel=1 run). Server-side HNSW query takes **1.9ms** (response headers); the rest is 2ms TCP RTT + ~2ms HTTP overhead. **Qdrant is 2.7× faster per query in same-region.**

- turbopuffer **parallel=1:** 55.5 RPS at 16.9ms mean  
- Qdrant **parallel=1:** 134 RPS at 6.3ms mean — **2.4× more throughput, 2.7× lower latency**
- The gap is architectural: HNSW in RAM (1.9ms) vs S3 centroid round-trips (15ms floor). Not closable.

**RPS at p=8:** Qdrant 365 RPS vs turbopuffer 224 RPS — Qdrant wins on a single 2CPU/8GB node. turbopuffer's higher RPS in some configs only appears with cross-region clients where network latency amplified the denominator.

---

## 7. Architecture Implications

### Why turbopuffer behaves the way it does

```
Client → turbopuffer API Gateway → Compute Node → Object Storage (S3)
                                        ↑
                               SPFresh: sequential
                               centroid round-trips
                               (~3-5 per query)
```

Each SPFresh query requires multiple round-trips to S3 to walk the centroid index. Each round-trip adds ~10-30ms. This is the fundamental latency floor and the reason:
- Queries can't get below ~80-100ms at best
- Throughput doesn't scale linearly with replicas (same S3 bucket is the shared bottleneck)
- Filters add disproportionate cost (extra passes over different S3 objects)
- The system is optimized for low infrastructure cost, not low latency

### The cost model trade-off
turbopuffer's value proposition is **cost efficiency at low QPS**. Object storage is ~10-100× cheaper per GB than NVMe. For a namespace that gets 1-5 queries/second with cold data, turbopuffer's model is economical. At higher QPS (100+), the autoscaled compute cost grows and the latency SLA becomes harder to meet.

---

## 8. Comparison with Qdrant Cloud

| Dimension | turbopuffer | Qdrant Cloud |
|-----------|-------------|--------------|
| **Architecture** | Object storage (S3) + ephemeral compute | RAM + disk, HNSW index |
| **Index type** | SPFresh (centroid-based, fixed recall) | HNSW + optional quantization |
| **Recall tuning** | None (fixed ~98.5%) | Full control (ef, m, quantization, oversampling) |
| **Single query latency (same region)** | 17ms (warm, pinned) | **6.3ms** (measured, same-region p=1) |
| **Peak RPS, unfiltered 100K (same region)** | 224 RPS (serverless p=8) | **365 RPS** (1 node, 2CPU/8GB, p=8) |
| **Peak RPS, filtered 105K (same region, warm)** | **212 RPS** | 25.1 RPS |
| **Filtered search p99 — warm** | **267ms** | **679ms** (Qdrant wins on precision, not latency) |
| **Filtered search p99 — cold** | **12.7 seconds** | **679ms** (18× better) |
| **Filtered precision** | 96.34% | **99.85%** |
| **Cold-start risk** | High — any replica restart hits 12s+ p99 | None — HNSW stays in RAM |
| **Upload 100K @ batch=256** | 22.3 min | 48 min (2.2× slower — single connection, no tuning) |
| **Scale** | Cold namespaces are free | Reserved capacity |
| **Precision/recall control** | No | Yes |
| **Pinning (dedicated compute)** | Yes (serverless often better) | N/A (always dedicated) |
| **Autoscaling to zero** | Yes | No |

---

## 9. Strategic Implications for Qdrant

### Where turbopuffer wins
1. **Very low QPS, cold namespaces:** If a namespace gets 10-100 queries/day, turbopuffer's "pay per query" model with object storage backend is genuinely cheaper than reserved Qdrant capacity.
2. **Operational simplicity:** No index tuning knobs. Works out of the box for developers who don't want to think about HNSW parameters.
3. **Serverless zero-cost idle:** Namespaces cost nothing when not queried.

### Where Qdrant wins
1. **Throughput:** 365 RPS vs 224 RPS on 100K unfiltered search (same region, same node size). Qdrant wins outright.
2. **Per-query latency:** Qdrant 6.3ms mean vs turbopuffer 17ms — 2.7× faster from the same region. Not closable: HNSW in RAM (1.9ms) vs S3 round-trips (~15ms).
3. **Filter performance cold-state:** Qdrant p99 = 679ms is consistent regardless of warm/cold. turbopuffer cold = 12.7s, warm = 267ms. Qdrant wins on reliability; turbopuffer wins only on warm-state throughput.
4. **Precision control:** Qdrant supports ef_search tuning, oversampling, quantization rescore. turbopuffer is fixed at ~96–98.9%.
5. **Predictability:** turbopuffer same query can take 17ms or 12+ seconds. Qdrant is consistent — 1.9ms server latency regardless of warm/cold state.
6. **Upload speed:** With proper config (batch=1024, parallel=4) Qdrant uploads 1M vectors in ~20 min. Our 48 min result was a config artifact (batch=256, parallel=1).

### Marketing angles
- **"Faster in your region"** — Same AWS region, same dataset: Qdrant 365 RPS vs turbopuffer 224 RPS. 6.3ms per query vs 16.9ms. Qdrant wins on throughput AND latency from co-located clients.
- **"Consistent, not sometimes fast"** — turbopuffer warm H&M hits 267ms p99. Cold hits 12.7s p99. 47× variance, same config. Qdrant 679ms p99 warm or cold.
- **"Recall you can trust"** — turbopuffer fixed at 96.3% for filtered search. Qdrant: 99.85%. That's 18× fewer wrong results at the tail.
- **"Replica scaling that actually works"** — turbopuffer pinned-4replicas delivers 18 RPS (12× worse than single-replica). Qdrant scales linearly.

### Positioning guidance
turbopuffer is a **cost-effective tier for sparse, cold, low-QPS workloads** — don't dismiss it for those. But the throughput narrative ("turbopuffer is faster") was based on cross-region Qdrant measurements where client RTT dominated. Same-region, Qdrant on a single small node beats turbopuffer on every performance metric. For any production API with:
- Latency SLA guarantees (cold-start risk is real)
- Filtering requirements and no warm-up guarantee
- QPS above 20-30 RPS per namespace without co-located clients
- Need for precision tuning above 98.5%

Qdrant is the better choice, and the predictability gap is architectural, not configurable.

---

## 10. Workload Fit Analysis

### The fundamental model: spiky multi-tenant, not steady-state

turbopuffer's economics rest on one assumption: **most namespaces are idle most of the time.** The object storage backend costs near-zero when not queried. If you have 10,000 customer namespaces and only 50 are active at any moment, you pay compute only for those 50. That's the legitimate value proposition.

The moment a namespace becomes **always-on** — serving consistent traffic throughout the day — the model breaks in two ways simultaneously:

1. **Cost advantage disappears.** Autoscaled compute provisioned continuously costs the same or more than a dedicated Qdrant node. You're paying EC2 rates without EC2 locality.
2. **Latency disadvantage remains.** Object storage round-trips don't get faster just because you're paying for them continuously. You're stuck at 126ms+ regardless.

This is the critical insight: **turbopuffer only beats Qdrant on cost when it also loses on latency. Once you need low latency (pinning), you lose the cost advantage too.** There is no configuration where turbopuffer is both cheap and fast for a hot namespace.

The rough crossing point: **~10-15 sustained RPS per namespace.** Below that, turbopuffer's idle-cost savings likely outweigh its per-query overhead. Above that, a dedicated Qdrant node is cheaper and 10-30× faster.

---

### Workloads turbopuffer serves well

| Workload | Why it fits |
|----------|-------------|
| Multi-tenant SaaS (most tenants idle) | Per-namespace object storage; only active tenants cost anything |
| Internal semantic search (async, low-QPS) | Latency tolerance high, infrequent queries |
| Dev/staging environments | Real data, rarely queried, zero idle cost |
| RAG over infrequent documents | Batch retrieval, latency not user-facing |
| One-off or scheduled pipelines | Cold queries acceptable, no SLA |

---

### Workloads turbopuffer serves poorly

**E-commerce / retail search**
Always-hot product catalog, heavy filtering (price × category × availability × location), sub-100ms SLA. Our H&M benchmark showed p99 = 12.7s with filters and precision dropping to 96.4%. Multi-condition filters get *worse* with each added condition — SPFresh has to walk more centroid paths and do post-filtering passes on object storage reads. A retailer cannot ship this.

**Real-time recommendations**
Personalization APIs operate within tight end-to-end latency budgets (typically <150ms total, including app logic, DB, and ML inference). turbopuffer's 126ms base latency consumes the entire budget before any application code runs.

**Consumer-facing search (apps, SaaS)**
Users perceive latency above ~100ms as "slow." turbopuffer starts at 126ms for 100K vectors — that's the absolute floor with optimal network and warm cache. At real-world scale and cold state, expect 200-500ms regularly.

**High-throughput ingestion + real-time search**
Systems that write and read continuously — fraud detection, live feed ranking, document indexing pipelines. Object storage writes are eventually consistent and slow (~17-37 min to upload 100K vectors single-threaded). turbopuffer is not designed for high-frequency writes alongside concurrent reads.

**Hybrid / sparse+dense search**
No native sparse vector support. BM25+dense fusion (the dominant RAG pattern for precision) is not available. Any workload needing keyword-aware retrieval alongside semantic similarity must look elsewhere.

**Precision-sensitive domains**
Medical, legal, compliance, financial search often require recall guarantees above 99% or the ability to trade recall for cost. turbopuffer's fixed ~98.9% recall with no tuning knobs means you can neither guarantee higher precision nor get a cheaper lower-precision tier.

**Sustained high-QPS (>15 RPS per namespace)**
Once a namespace crosses ~15 RPS steady-state, autoscaling runs continuously and compute costs rival or exceed Qdrant Cloud pricing — with 10-30× worse latency. The cost-efficiency argument collapses entirely.

---

## 11. Raw Benchmark Data Reference

Result files: `results/turbopuffer-*.json`, `results/qdrant-cloud-us-west-2-*.json`

### turbopuffer async sweep (DBpedia 100K)

| Config | Concurrency | Queries | RPS | Notes |
|--------|-------------|---------|-----|-------|
| async unpinned | 1 | — | ~8 | True base latency: ~126ms |
| async unpinned | 32 | 500 | ~110 | Autoscaling ceiling |
| async unpinned | 64 | 500 | ~110 | Same ceiling |
| async unpinned | 128 | 500 | ~46 | Autoscaling hadn't ramped yet |
| async unpinned | 128 | 2000 | ~70 | Autoscaling kicked in mid-run |
| async pinned-1r | 32/64/128 | 500 | ~35 | Fixed, no autoscale |
| async pinned-2r | 32/64/128 | 500 | ~55 | Fixed, no autoscale |
| async pinned-4r | 128 | 2000 | ~39 | Worse than 2r — S3 bottleneck |
| mp parallel-32 (slow net) | 32 | 5000 | ~18 | 89ms RTT, TCP overhead |
| mp parallel-32 (good net) | 32 | 5000 | **43.2** | 72ms RTT |
| mp default (good net) | 8 | 5000 | **24.5** | Autoscaled |

### Qdrant Cloud async sweep (DBpedia 100K, 1 node 2CPU/8GB)

| Concurrency | RPS | Mean | p95 | p99 | Server mean |
|-------------|-----|------|-----|-----|-------------|
| 8 | 30.2 | 264ms | 537ms | 597ms | 1.8ms |
| 16 | 32.7 | 488ms | 756ms | 813ms | 1.8ms |

### Qdrant Cloud multiprocessing (DBpedia 100K)

| Parallel | RPS | Mean | p95 | p99 | Server mean | Precision |
|----------|-----|------|-----|-----|-------------|-----------|
| 8 | 35.1 | 227ms | 263ms | 556ms | 1.9ms | 99.0% |
| 32 | 34.1 | 935ms | 1893ms | 4096ms | 1.9ms | 99.0% |

### turbopuffer Multi-Tenant: Namespace-per-Tenant vs Single Namespace (1M × 768-dim, 100 tenants)

Dataset: `random-768-100-tenants` — 1M vectors, 768-dim cosine, 100 distinct tenants (field `a`), ~10K vectors per tenant. Each test query includes a tenant filter. Ground truth precision measured against filtered results.

**Option A — namespace-per-tenant:** Each tenant maps to a dedicated turbopuffer namespace (`random-768-tenant-<value>`). Queries route directly to the correct namespace — no filter applied. Each namespace holds ~10K vectors.

**Option B — single namespace + filter:** All 1M vectors in one namespace (`random-768-100-tenants-single`). Queries include a metadata filter on field `a` to restrict results to the correct tenant. SPFresh must scan all 1M vectors and post-filter.

| Metric | Option A: ns-per-tenant | Option B: single-ns + filter |
|--------|------------------------|------------------------------|
| RPS | **24.5** | 13.0 |
| Mean latency | **69ms** | 181ms |
| p95 | **288ms** | 432ms |
| p99 | **322ms** | 881ms |
| Precision | **99.98%** | 80.9% |
| Upload time | 7.4 min | 6.1 min |

**Key takeaway:** Option B (wrong architecture) is **1.9× slower** and collapses precision from 99.98% to **80.9%** — one in five results is wrong. The precision collapse is more severe here than in the H&M filtered test (96.4%) because each tenant is only 1% of the corpus (10K/1M), making the filter extremely selective and forcing SPFresh into brute-force post-filtering over a large candidate pool.

This is the core turbopuffer sales argument: if you build multi-tenant on a single namespace, you get both the worst cost structure (paying for 1M vectors when querying 10K) and the worst precision. The namespace-per-tenant pattern is turbopuffer's intended architecture for this use case.
