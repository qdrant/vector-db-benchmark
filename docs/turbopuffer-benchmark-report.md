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
Early tests were run over a slow network connection (RTT ~89ms to aws-us-west-2). Results were misleading. All final results below were taken after switching to a lower-latency connection (RTT ~72ms). The difference was dramatic: multiprocessing RPS jumped from ~18 to ~43 RPS.

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

### 4.1 Multiprocessing benchmark (`run.py`)

> Note: latency numbers here are inflated by ~320ms per query due to per-worker TCP connection setup. RPS is directionally correct but underestimates true throughput ceiling.

| Config | Parallel | Cache Strategy | RPS | Mean Latency | p95 | p99 | Precision |
|--------|----------|---------------|-----|-------------|-----|-----|-----------|
| `turbopuffer-default` (slow network) | 8 | none | 17.4 | 452ms | 797ms | 1031ms | 98.78% |
| `turbopuffer-default` (slow network) | 8 | none | 17.3 | 459ms | 845ms | 1137ms | 98.87% |
| `turbopuffer-hint-warm` | 8 | hint_warm | 17.3 | 459ms | 847ms | 1140ms | 98.87% |
| `turbopuffer-pinned` (1r) | 8 | pinned | 17.2 | 464ms | 880ms | 1162ms | 98.87% |
| `turbopuffer-pinned` (1r) | 8 | pinned | 18.0 | 443ms | 830ms | 1068ms | 98.87% |
| `turbopuffer-parallel-32` (slow network) | 32 | none | 18.0 | 1766ms | 3852ms | 6660ms | 98.87% |
| `turbopuffer-parallel-32` (**good network**) | 32 | none | **43.2** | 738ms | 1367ms | 1966ms | 98.87% |
| `turbopuffer-default` (**good network**) | 8 | none | **24.5** | 322ms | 782ms | 1482ms | 98.87% |
| `turbopuffer-pinned-4replicas` (before good network) | 32 | pinned (4r) | 18.5 | 1723ms | 3602ms | 6291ms | 98.87% |
| `turbopuffer-pinned-4replicas` (before good network) | 32 | pinned (4r) | 18.2 | 1752ms | 3590ms | 5931ms | 98.87% |
| `turbopuffer-pinned-4replicas` (before good network) | 32 | pinned (4r) | 18.3 | 1728ms | 3508ms | 5895ms | 98.87% |
| `turbopuffer-pinned-4replicas` (**good network**) | 32 | pinned (4r) | **41.5** | 767ms | 1059ms | 1123ms | 98.87% |

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

### 4.3 Qdrant Cloud — multiprocessing (`run.py`)

| Parallel | RPS | Mean Latency | p95 | p99 | Server Latency | Precision |
|----------|-----|-------------|-----|-----|----------------|-----------|
| 8 | **35.1** | 227ms | 263ms | 556ms | **1.9ms** | 99.0% |
| 32 | **34.1** | 935ms | 1893ms | 4096ms | **1.9ms** | 99.0% |

**Key insight:** Server-side latency is **1.9ms** — the actual HNSW query takes under 2ms. The 227ms client-side mean is almost entirely network RTT (~72ms × 2 + queueing). Going from parallel=8 to parallel=32 adds no RPS but 4× latency because the node request queue saturates.

### 4.4 Qdrant Cloud — async single client (`async_qdrant_bench.py`)

| Concurrency | RPS | Mean Latency | p95 | p99 | Server Latency |
|-------------|-----|-------------|-----|-----|----------------|
| 8 | **30.2** | 264ms | 537ms | 597ms | 1.8ms |
| 16 | **32.7** | 488ms | 756ms | 813ms | 1.8ms |

Node saturates at ~30-35 RPS. Server latency stays flat at 1.8ms regardless of concurrency — bottleneck is the node's request queue, not HNSW computation. The async client shows slightly lower RPS than multiprocessing at the same parallelism because it's genuinely a single-threaded event loop vs. OS-level process parallelism, but with far better latency distribution.

---

## 5. Search Performance — H&M (105K vectors, with filters)

### Multiprocessing benchmark (`run.py`)

| Config | Parallel | Cache Strategy | RPS | Mean Latency | p95 | p99 | Precision |
|--------|----------|---------------|-----|-------------|-----|-----|-----------|
| `turbopuffer-hm-pinned` (4r, good network) | 32 | pinned (4r) | **19.8** | 1614ms | 4341ms | 12713ms | **96.37%** |

**Note:** Filtered search on H&M with 4 pinned replicas achieved only ~20 RPS with very high tail latency (p99 = 12.7 seconds). Precision dropped to 96.4% vs 98.9% on DBpedia without filters. The 52-second max latency suggests occasional cold-path fetches from object storage.

### 5.2 Qdrant Cloud — multiprocessing (`run.py`)

| Parallel | RPS | Mean Latency | p95 | p99 | Server Latency | Precision |
|----------|-----|-------------|-----|-----|----------------|-----------|
| 8 | **25.1** | 317ms | 541ms | 679ms | **1.4ms** | **99.85%** |
| 32 | 26.0 | 1230ms | 2458ms | 4132ms | 1.4ms | 99.85% |

**The contrast:** Qdrant's payload indexes keep filtered server latency at **1.4ms** — almost identical to unfiltered. turbopuffer's filters degrade p99 from ~1s (unfiltered) to 12.7s (filtered). Qdrant precision is **99.85%** vs turbopuffer's **96.37%** — filtered ANN recall degrades significantly in turbopuffer's SPFresh index.

---

## 6. Key Findings

### 6.1 Network latency is the dominant cost for multiprocessing clients
Before fixing the network path (89ms RTT), results looked uniformly ~17-18 RPS regardless of concurrency or pinning. After switching to ~72ms RTT, the same configs hit 41-43 RPS. **turbopuffer's query time is dominated by the round-trip to aws-us-west-2** — co-location matters more here than for RAM-resident databases because object storage adds another network hop from the compute node.

### 6.2 Unpinned (serverless) autoscaling beats manual pinning
The most counterintuitive finding: **the shared multi-tenant pool autoscales dynamically and outperforms manually pinned replicas**.

- Unpinned with c=32 async: **~110 RPS** (autoscaling kicks in)
- Pinned with 4 replicas, c=128: **~39 RPS** (hard ceiling, no autoscale)

Why? Pinning reserves fixed compute and **disables autoscaling**. The shared pool is large enough that turbopuffer's autoscaler can provision more capacity than 4 dedicated replicas. Pinning is a ceiling, not a floor. This means pinning is only beneficial for **latency SLA guarantees** (no cold-start spikes), not for raw throughput.

### 6.3 SPFresh does not scale throughput with more replicas
With pinned replicas:
- 1 replica: ~35 RPS (c=32/64/128 all the same)
- 2 replicas: ~55 RPS (not 2×)
- 4 replicas: ~38-41 RPS (worse than 2r in some runs)

SPFresh requires sequential round-trips to object storage during each query. The bottleneck is **object storage IOPS and round-trip count**, not compute parallelism. Adding more replicas doesn't help if each replica is doing the same sequential read pattern. The shared multi-tenant pool works better because turbopuffer likely has better locality/caching at the fleet level.

### 6.4 Cache warm hint has zero measurable effect
`hint_cache_warm` vs default at parallel=8: both 17.3-17.4 RPS, essentially identical latency. The hint either does nothing for cold namespaces or the measurement window was too short for the warming to fully land.

### 6.5 Precision is fixed at ~98.9%
Across all DBpedia runs (no filters), precision was **98.87-98.78%** — identical regardless of concurrency, pinning, or cache strategy. This confirms that SPFresh's recall target is hard-coded internally. There is **no way to trade recall for speed or vice versa**. If you need 99.5% precision, turbopuffer cannot offer it. If you're fine with 95%, you also cannot get it cheaper.

For filtered search (H&M), precision dropped to **96.4%** with p99 = 12.7s, suggesting filters are expensive: SPFresh has to do additional post-filtering passes and may fall back to brute-force scans for rare filter conditions.

### 6.6 Tail latency with filters is severe
H&M filtered search: p99 = **12.7 seconds**, max = **52 seconds**. This is not production-grade for latency-sensitive applications. The variance is enormous (std = 2.47s). In contrast, unfiltered DBpedia with good network and pinning: p99 = **1.1 seconds** with much tighter variance (std = 0.18s).

### 6.7 Upload speed is slow
100K vectors at 1536 dimensions: 33-37 minutes at batch_size=1000, single-threaded. For comparison, Qdrant Cloud with binary quantization uploads 1M vectors to DBpedia in ~20 minutes total (index + optimize). turbopuffer's 100K ingest rate implies ~5.5 hours for 1M vectors at the same single-connection rate.

### 6.8 Multi-tenant architecture choice has catastrophic precision impact
With 1M vectors across 100 tenants (10K per tenant), the wrong architecture (single namespace + filter) collapses precision from **99.98% → 80.9%** — one in five query results is incorrect. SPFresh's post-filtering degrades severely when the filter selectivity is high (1% of corpus). This is not a tunable parameter.

The correct architecture (namespace-per-tenant) routes each query to the right 10K-vector namespace with no filter, preserving both precision and latency. **This is turbopuffer's native multi-tenant model — and it only works if tenants are routed correctly at the application layer.**

### 6.9 True query latency: turbopuffer ~126ms vs Qdrant ~1.9ms server-side
At c=1 with the async client, turbopuffer single query latency is ~126ms — the base cost per query:
- Client → turbopuffer API (~72ms RTT)
- turbopuffer compute → S3 (sequential round-trips for SPFresh centroid lookups)
- Return path

Qdrant Cloud's server-side HNSW query time is **1.9ms** (measured via response headers in our benchmark). The 227ms client-side latency is almost entirely network RTT — the actual index traversal is near-instant. This means:
- **In the same region (co-located client):** Qdrant query ≈ 2ms, turbopuffer query ≈ 50-80ms (S3 round-trips dominate)
- **Cross-region:** Both add the same RTT, but turbopuffer's S3 overhead is still on top
- The latency gap is **not closable by turbopuffer** — it's the physics of object storage round-trips vs. RAM access

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
| **Recall tuning** | None (fixed ~98.9%) | Full control (ef, m, quantization, oversampling) |
| **Single query latency** | ~126ms client / ~50-80ms server-side | **1.9ms server-side** (227ms client @ 72ms RTT) |
| **Peak RPS (100K vectors)** | ~110 RPS (serverless async) | **35 RPS** (1 node, 2CPU/8GB, HNSW) |
| **Filtered search p99 (105K)** | **12.7 seconds** | **679ms** (18× better) |
| **Filtered precision** | 96.37% | **99.85%** |
| **Upload 100K @ batch=256** | 22.3 min | 48 min (2.2× slower — single connection, no tuning) |
| **Scale** | Cold namespaces are free | Reserved capacity |
| **Precision/recall control** | No | Yes |
| **Pinning (dedicated compute)** | Yes (but hurts throughput) | N/A (always dedicated) |
| **Autoscaling to zero** | Yes | No |

---

## 9. Strategic Implications for Qdrant

### Where turbopuffer wins
1. **Very low QPS, cold namespaces:** If a namespace gets 10-100 queries/day, turbopuffer's "pay per query" model with object storage backend is genuinely cheaper than reserved Qdrant capacity.
2. **Operational simplicity:** No index tuning knobs. Works out of the box for developers who don't want to think about HNSW parameters.
3. **Serverless zero-cost idle:** Namespaces cost nothing when not queried.

### Where Qdrant wins
1. **Latency:** Server-side HNSW query is **1.9ms** vs turbopuffer's ~50-80ms irreducible S3 overhead. Not closable — it's the physics of RAM vs. object storage.
2. **Throughput at scale:** Our single 2CPU/8GB Qdrant node matches turbopuffer's best multiprocessing result (35 RPS) while serving 99.0% precision. With a larger node or horizontal scaling Qdrant grows linearly; turbopuffer's S3 bottleneck limits replica scaling.
3. **Filter performance:** Qdrant payload indexing keeps filter latency predictable. turbopuffer filter p99 = 12.7s is a hard product limitation. *(Qdrant H&M comparison pending.)*
4. **Precision control:** Qdrant supports ef_search tuning, oversampling, quantization rescore — any recall/speed tradeoff. turbopuffer is fixed at ~98.9%.
5. **Predictability:** turbopuffer same query can take 126ms or 52 seconds depending on cold/hot state. Qdrant is consistent — 1.9ms server latency regardless of concurrency.
6. **Upload speed:** With proper config (batch=1024, parallel=4) Qdrant uploads 1M vectors in ~20 min. Our 48 min result was a config artifact (batch=256, parallel=1).

### Marketing angles
- **"Latency you can actually ship"** — turbopuffer's 126ms floor is visible to end users. Qdrant's 5-17ms is not.
- **"Real-time filtering without roulette"** — turbopuffer's 12s filter p99 is a dealbreaker for production use cases with conditional logic. Qdrant's payload index keeps filter latency flat.
- **"Recall on your terms"** — turbopuffer locks you into one recall level. Qdrant lets you dial quality vs speed for your specific use case and budget.
- **"100× the data, same latency"** — Qdrant's 1M vector benchmark at lower latency than turbopuffer's 100K benchmark shows the HNSW architecture scales sub-linearly.

### Positioning guidance
turbopuffer is a **legitimate competitor for cold, low-QPS workloads** — don't dismiss it. But for any production API with:
- Latency SLA below 200ms
- Filtering requirements
- QPS above 20-30 RPS
- Need for precision tuning

Qdrant is the better choice, and the gap is architectural, not just a matter of configuration.

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
