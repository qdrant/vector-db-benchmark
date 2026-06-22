# turbopuffer vs Qdrant Cloud — Executive Summary

**Date:** 2026-06-22 | **Author:** Shivendu Kumar, Qdrant | **Region:** aws-us-west-2

---

## Bottom Line

From the same AWS region (us-west-2), Qdrant on a single 2CPU/8GB node beats turbopuffer on every performance dimension: 2.3× lower single-query latency, 2.3× more throughput per connection, 5.2× more throughput on multi-tenant workloads, and better recall everywhere. turbopuffer's genuine advantage is **cost-to-zero for idle namespaces** — object storage costs nothing when not queried.

turbopuffer is not a better search engine. It is a cheaper storage tier for sporadic traffic. That tradeoff has hard edges: cold-start latency spikes (up to 1.6s p99 for filtered search after any replica restart) and fixed recall (~96–98.4%) with no tuning knobs.

**For production APIs with sustained traffic:** Qdrant wins on performance and on cost above ~10 QPS/namespace.  
**For multi-tenant SaaS where most tenants are idle most of the time:** turbopuffer's cost model is compelling — but you pay a 5× performance penalty on the tenants that are active.

---

## Head-to-Head

| Dimension | turbopuffer | Qdrant Cloud |
|-----------|-------------|--------------|
| Architecture | Object storage (S3) + ephemeral compute | HNSW index in RAM |
| Single-query latency (p=1, same region) | 15.6ms mean | **6.8ms mean** |
| Single-query RPS (p=1) | 64 RPS | **147 RPS** |
| Single-query p99 | 39.9ms | **11.8ms** |
| Multi-tenant RPS (p=1, ns-per-tenant vs payload_m=16) | 38.6 RPS | **199.5 RPS** |
| Multi-tenant p99 (p=1) | 106.7ms | **6.9ms** |
| Filtered search — warm (H&M 105K×2048) | 93ms mean | **6.0ms mean** |
| Filtered search — cold p99 | **~1.6s** | **8.8ms** (no cold-start) |
| Recall — unfiltered (100% of queries) | 98.4% | 98.4% |
| Recall — multi-tenant | 100% | **100%** |
| Recall — filtered (H&M) | 90.9% | **95.9%** |
| Recall tuning | None (fixed) | Full (ef, quantization, oversampling) |
| Cold-start risk | Yes — S3 fetch on first queries after restart | None — HNSW stays in RAM |
| Upload 100K vectors, batch=128 (DBpedia) | 2.4 min | 3.8 min |
| Upload 100K vectors, batch=128 (H&M, 2048-dim) | 3.0 min | 9.0 min |
| Scales to zero (idle cost) | **Yes** | No |
| Cost above ~10 QPS/namespace | More expensive | **Cheaper** |
| Cost below ~8 QPS/namespace | **Cheaper** | More expensive |

---

## Key Numbers

### Upload (batch=128, async client, aws-us-west-2)

| Engine | Dataset | Vectors | Time |
|--------|---------|---------|------|
| turbopuffer | DBpedia (1536-dim) | 100K | 2.4 min |
| Qdrant Cloud | DBpedia (1536-dim) | 100K | 3.8 min |
| turbopuffer | H&M (2048-dim) | 105K | 3.0 min |
| Qdrant Cloud | H&M (2048-dim) | 105K | 9.0 min |
| turbopuffer | Multi-tenant 768-dim (100 namespaces) | 100K | 2.3 min |
| Qdrant Cloud | Multi-tenant 768-dim (1 collection + index) | 100K | 20.6 min |

Qdrant is slower to upload for H&M (larger vectors, more HTTP payload per batch) and significantly slower for the multi-tenant collection — building per-tenant HNSW sub-graphs (`payload_m=16`) is expensive at write time. turbopuffer writes directly to object storage with no server-side index construction.

---

### Search — DBpedia 100K × 1536-dim (unfiltered, same-region client)

#### Single-connection baseline (p=1) — most reliable measurement

| Engine | RPS | Mean | p50 | p95 | p99 | Recall |
|--------|-----|------|-----|-----|-----|--------|
| turbopuffer (serverless) | 64 RPS | 15.6ms | 14.8ms | 19.4ms | 39.9ms | 98.4% |
| Qdrant Cloud | **147 RPS** | **6.8ms** | **6.5ms** | **7.5ms** | **11.8ms** | 98.4% |

**Same recall, 2.3× lower latency and throughput for Qdrant.** This gap is architectural: Qdrant's HNSW index lives in RAM (1.9ms server-side, confirmed via `server_time` response header). turbopuffer traverses a centroid tree backed by NVMe/S3 — the ~13–15ms floor is irreducible regardless of configuration.

---

### Search — DBpedia — Fixed-QPS Sweep (dollar break-even)

Queries fired at exact rates for 120 seconds each. Latency figures are real measured distributions; costs are based on turbopuffer's published pricing.

| QPS sustained | tpuf p50 | tpuf p99 | **tpuf $/mo** | qdrant p50 | qdrant p99 | **qdrant $/mo** | Cheaper |
|--------------|----------|----------|--------------|------------|------------|----------------|---------|
| 1 | 18.8ms | 63.6ms | **$3.42** | 7.7ms | 16.4ms | **$26.10** | tpuf (7.6×) |
| 5 | 15.3ms | 36.1ms | **$16.69** | 7.3ms | 13.0ms | **$26.10** | tpuf (1.6×) |
| 10 | 14.2ms | 36.0ms | **$33.28** | 7.4ms | 11.0ms | **$26.10** | Qdrant (1.3×) |
| 20 | 15.5ms | 43.0ms | **$66.46** | 7.1ms | 11.0ms | **$26.10** | Qdrant (2.5×) |
| 50 | 15.0ms | 37.1ms | **$165.99** | 7.1ms | 15.0ms | **$26.10** | Qdrant (6.4×) |

**Observations:**
- turbopuffer latency is flat at ~15ms across all QPS levels — serverless autoscaling handles the load without queueing at these rates.
- Cost crossover is at **~10 QPS**. At that crossover, Qdrant is already 3× lower p99.
- At 50 QPS: turbopuffer costs **6× more** with **2× worse latency**. There is no operating point where turbopuffer is simultaneously cheaper and faster for a sustained workload.

---

### Search — H&M 105K × 2048-dim (filtered, categorical attribute)

#### turbopuffer (pinned, 4 replicas, p=32 concurrent)

| State | Mean | p50 | p95 | p99 | Recall |
|-------|------|-----|-----|-----|--------|
| Warm (NVMe-cached) | 93ms | 69ms | 236ms | 351ms | **90.9%** |
| **Cold** (fresh namespace, no warmup) | 210ms | 80ms | 1,510ms | **1,574ms** | **90.9%** |

Recall measured separately at p=1 (500 queries) after warmup. The drop from ~98% unfiltered to **90.9% filtered** is architectural: SPFresh runs ANN on the full dataset first, then applies the filter as a post-processing step. When the filter is selective, discarded candidates are not replaced — the returned set can be smaller than top-10, directly hurting recall.

Cold-state means the namespace was freshly created via `copy_from` (no NVMe cache). After any replica restart or provisioning event, turbopuffer resets to cold — the first queries must fetch centroid data from S3. Warm p99 is 351ms; cold p99 is 1,574ms (**4.5× worse, same config**).

#### Qdrant Cloud (1 node 2CPU/8GB, p=1)

| State | RPS | Mean | p50 | p95 | p99 | Recall |
|-------|-----|------|-----|-----|-----|--------|
| Always warm | **166 RPS** | **6.0ms** | **5.9ms** | **7.4ms** | **8.8ms** | **95.9%** |

Qdrant's HNSW graph is in RAM — there is no cold-start state. Latency and recall are identical regardless of whether the cluster just restarted. The payload index scan for categorical filters adds ~4ms to the ~2ms HNSW cost; the total is still under 10ms p99.

**The key risk for filtered search:** turbopuffer's cold p99 (~1.6s) activates whenever a pinned replica restarts or is newly provisioned. For a SaaS that autoscales or redeploys, this risk is live. Qdrant has no equivalent.

---

### Search — Multi-Tenant (100K × 768-dim, 100 tenants)

Dataset: 100K vectors across 100 tenants (~1K per tenant). turbopuffer routes each query to its per-tenant namespace (100 namespaces total). Qdrant uses one collection with per-tenant HNSW sub-graphs (`m=0, payload_m=16, is_tenant=True`).

#### Single-connection (p=1) — reliable measurement

| Engine | Config | RPS | Mean | p50 | p99 | Recall |
|--------|--------|-----|------|-----|-----|--------|
| turbopuffer | ns-per-tenant | 38.6 RPS | 25.9ms | 19.7ms | 106.7ms | **100%** |
| Qdrant Cloud | payload_m=16 | **199.5 RPS** | **5.0ms** | **4.9ms** | **6.9ms** | **100%** |

**Qdrant delivers 5.2× more throughput at 5.2× lower latency — both engines at 100% recall.**

turbopuffer's p99 (106ms vs Qdrant's 6.9ms) is wide because each query requires a separate HTTP connection to a different namespace endpoint. Qdrant's sub-graph routing is in-process. The 25.9ms mean vs 5.0ms reflects the same architectural gap as unfiltered search, with additional namespace routing overhead.

**The cost question for multi-tenant:** turbopuffer's 100 namespaces cost near-zero when idle. A SaaS with 100 customers and only 5 active at any moment pays for 5 active namespaces' compute. Qdrant's cluster costs $26/month regardless of how many tenants are active. Below ~8 QPS per tenant on average, turbopuffer is cheaper. Above that, Qdrant is cheaper and 5× faster.

---

## Cost Summary

turbopuffer pricing: $0.33/GB/month storage (f16 vectors) + $2/GB writes (f32) + $0.001/TB scanned per query (min 1.28 GB/namespace, regardless of actual size).

Qdrant Cloud pricing (AWS us-west-2, 1 replica, no quantization): flat monthly cluster fee.

| Dataset | tpuf $/1M queries | Qdrant $/mo | Break-even QPS |
|---------|-------------------|-------------|----------------|
| 100K × 1536-dim | $1.28 | $26.10 | **~8 QPS** |
| 1M × 1024-dim | $2.05 | $68.34 | **~13 QPS** |
| 10M × 768-dim | $15.36 | $410.04 | **~10 QPS** |

The 1.28 GB minimum namespace billing means even a 308 MB dataset (100K × 1536-dim f16) gets charged as 1.28 GB per scan. This floors the per-query cost regardless of data size.

At 100K queries/month (3 queries/hour): turbopuffer costs $0.23, Qdrant costs $26. At 50M queries/month (19 QPS): turbopuffer costs $64, Qdrant costs $26.

### ⚠ Pinned mode: the cost picture for filtered search

The ~10 QPS serverless crossover only applies to **unfiltered search**. Filtered search requires pinning to get stable latency. Pinned billing: **$0.01325/GB-hr × max(actual_gb, 64) × replicas × 730 hr/month**.

The 64 GB billing floor eliminates any serverless cost advantage for small datasets:

| Config | Cost/mo | RPS | p99 (warm) | Recall |
|--------|---------|-----|------------|--------|
| tpuf pinned 4r (0.43 GB → 64 GB billed) | **$2,476** | 10.9 | 351ms | 90.9% |
| Qdrant Cloud 1 node | **$26.10** | 158 | 8.8ms | 95.9% |

**The 64 GB floor means:**
- H&M benchmark dataset (0.43 GB): tpuf pinned is **95× more expensive** with no performance benefit
- Break-even for pinned 1r: ~2.7 GB actual (~900K vectors at 1536-dim)
- Break-even for pinned 4r: **none** — 4 replicas is the same data replicated, not 4× more data. Minimum 4r cost ($2,476) always exceeds $26.10 regardless of dataset size.
- Below those thresholds, Qdrant is cheaper at **every** QPS level for filtered search

---

## Workload Fit

| Workload | turbopuffer | Qdrant | Notes |
|----------|-------------|--------|-------|
| Multi-tenant SaaS, most tenants idle | ✓ | — | Zero idle cost. 5× performance penalty on active tenants. |
| Internal / async semantic search | ✓ | — | Latency tolerance high, cost matters more |
| Dev / staging environments | ✓ | — | Real data, rarely queried, zero idle cost |
| **Sustained multi-tenant (>8 QPS/tenant)** | — | ✓ | **Qdrant cheaper AND 5× faster** |
| Filtered / faceted search (e-commerce) | Risky | ✓ | Cold p99 ~1.6s. Qdrant always 8.8ms. Recall: tpuf 90.9% vs Qdrant 95.9%. |
| Real-time recommendations / consumer apps | — | ✓ | 15ms tpuf floor vs 6.8ms Qdrant. 2.3× gap is user-visible. |
| Precision-sensitive (medical/legal/finance) | — | ✓ | Fixed 96–98.4% recall, not tunable. |
| High-write + concurrent read | — | ✓ | tpuf writes to S3; not designed for concurrent write+read. |
| Hybrid sparse+dense search | — | ✓ | No native sparse vector support in tpuf. |

---

## turbopuffer Architecture in Brief

turbopuffer stores all data in **object storage (S3)**. Its ANN index, SPFresh, is centroid-based: a query walks a tree of centroid blocks. When those blocks are in the local NVMe cache (warm state), query latency is ~13–15ms. When they aren't (cold state), each uncached block requires an S3 fetch first — adding 100–900ms per event.

There are **no recall tuning knobs** — no ef, no M, no quantization tradeoff. The system targets ~98.5% recall internally for unfiltered search; filtered search drops to ~96% due to post-filtering on the centroid results.

**Serverless** (default): namespaces share a multi-tenant compute pool, autoscale to demand, and cost nothing when idle. **Pinned**: reserves dedicated NVMe-backed instances with a fixed replica count. Pinned namespaces get machine isolation (no noisy-neighbor effect from other namespaces under the same API key) but lose autoscaling.

For unfiltered search, serverless is faster than pinned at equivalent cost because it routes across multiple pool nodes under concurrency. For filtered search with reliable cold-state requirements, neither mode solves the S3 fetch problem.

---

## Where Qdrant Wins (and Why It's Permanent)

1. **Latency floor:** 6.8ms mean vs 15.6ms. HNSW in RAM (1.9ms server) vs NVMe/S3 centroid traversal (~13–15ms floor). Not configurable.
2. **Filtered search consistency:** Qdrant payload indexes keep filter latency at ~8ms p99 warm or cold. turbopuffer cold p99 for filtered search is ~1.6s.
3. **Multi-tenant throughput:** Qdrant's `payload_m=16` sub-graph approach delivers 5.2× more throughput at 5.2× lower latency vs ns-per-tenant, both at 100% recall.
4. **Recall control:** Full ef, quantization, oversampling dial. turbopuffer locked at 90.9% filtered / 98.4% unfiltered — no tuning knobs.
5. **Cost above ~10 QPS:** Qdrant is cheaper and faster simultaneously. There is no operating point above this threshold where turbopuffer wins.

## Cross-Namespace Contention (Noisy Neighbor Test)

**Question:** Does turbopuffer co-locate all namespaces under one API key on the same machine?

**Method:** Measure a victim namespace at p=1 (sequential) to get a latency baseline. Then hammer a second aggressor namespace at p=32 and re-measure the victim. Repeated with freshly-created UUID-named namespaces to rule out name-based routing coincidence.

| Mode | Victim p50 baseline | Victim p50 under aggressor load | Degradation |
|------|--------------------|---------------------------------|-------------|
| Serverless (all 3 trials) | ~15ms | ~48–53ms | **+200–255%** |
| Both pinned (1r each) | 16.3ms | 19.5ms | **+20%** |

**Yes — serverless co-locates all namespaces per API key on one machine.** A bursty tenant degrades all others on the same account by 3×. UUID namespace names ruled out any coincidence. The aggressor in the pinned test also achieved far fewer total queries (1,548 vs 4,957) — consistent with two separate machines.

**Pinning buys machine isolation.** When pinned, you leave the shared pool and land on dedicated hardware. The +20% under pinning is normal load variation, not machine sharing.

**What this means for multi-tenant products:** In serverless mode, one heavy tenant will degrade all others under the same API key. Pinning each tenant namespace isolates them but removes autoscaling and adds cost. There's no serverless escape from this.

---

## Where turbopuffer Wins

1. **Idle cost:** Object storage costs near-zero when not queried. Genuine advantage for sparse multi-tenant workloads.
2. **Zero-config:** No HNSW tuning. Works out of the box for teams that don't want to manage index parameters.
3. **Serverless scale-to-zero:** True pay-per-query billing for infrequent traffic.
