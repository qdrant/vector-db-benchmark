# turbopuffer vs Qdrant Cloud — Executive Summary

**Date:** 2026-06-22 | **Author:** Shivendu Kumar, Qdrant | **Region:** aws-us-west-2

---

## Bottom Line

From the same AWS region (us-west-2), Qdrant on a single 2CPU/8GB node beats turbopuffer on every performance dimension: 2.5× lower single-query latency, 2.5× more throughput per connection, 5.5× more throughput on multi-tenant workloads, and better recall everywhere. turbopuffer's genuine advantage is **cost-to-zero for idle namespaces** — object storage costs nothing when not queried.

turbopuffer is not a better search engine. It is a cheaper storage tier for sporadic traffic. That tradeoff has hard edges: cold-start latency spikes (up to 1.9s p99 for filtered search after any replica restart) and fixed recall (~89–98.5%) with no tuning knobs.

**For production APIs with sustained traffic:** Qdrant wins on performance and on cost above ~10 QPS/namespace.  
**For multi-tenant SaaS where most tenants are idle most of the time:** turbopuffer's cost model is compelling — but you pay a 5× performance penalty on the tenants that are active.

---

## Head-to-Head

| Dimension | turbopuffer | Qdrant Cloud |
|-----------|-------------|--------------|
| Architecture | Object storage (S3) + ephemeral compute | HNSW index in RAM |
| Server-side latency floor | ~10–19ms (NVMe centroid traversal) | **~1.9ms** (HNSW RAM lookup) |
| Single-query latency (p=1, same region) | 15.9ms p50 | **6.9ms p50** |
| Single-query RPS (p=1) | 57.1 RPS | **143.2 RPS** |
| Single-query p99 | 47.1ms | **8.4ms** |
| Multi-tenant RPS (p=1, ns-per-tenant vs payload_m=16) | 33.5 RPS | **184.6 RPS** |
| Multi-tenant p99 (p=1) | 119.6ms | **9.7ms** |
| Filtered search — warm (H&M 105K×2048) | 139ms mean / server_p50 119ms | **6.1ms mean** |
| Filtered search — cold p99 | **~1.9s** | **10.1ms** (no cold-start) |
| Recall — unfiltered (100% of queries) | 98.51% | 98.36% |
| Recall — multi-tenant | 100% | **100%** |
| Recall — filtered (H&M) | 88.94% | **95.71%** |
| Recall tuning | None (fixed) | Full (ef, quantization, oversampling) |
| Cold-start risk | Yes — S3 fetch on first queries after restart | None — HNSW stays in RAM |
| Upload 100K vectors, batch=128 (DBpedia) | 2.7 min (624 wps) | 3.9 min (428 wps) |
| Upload 100K vectors, batch=128 (H&M, 2048-dim) | 3.1 min (574 wps) | 9.0 min (304 wps) |
| HNSW index build (H&M) | none | 195.8s one-time |
| Server-side latency p99 | DBpedia 40ms, H&M warm 472ms, H&M cold 1,777ms | **2.5ms (flat)** |
| Data scanned per query | ~full dataset (0.615–0.872 GB) | N/A (index lookup) |
| Scales to zero (idle cost) | **Yes** | No |
| Cost above ~10 QPS/namespace | More expensive | **Cheaper** |
| Cost below ~8 QPS/namespace | **Cheaper** | More expensive |

---

## Key Numbers

### Upload (batch=128, async client, aws-us-west-2)

| Engine | Dataset | Vectors | Total time† | Throughput | Extra index wait‡ | Stored GB§ |
|--------|---------|---------|------|------------|------------|---------------|
| turbopuffer | DBpedia (1536-dim) | 100K | 2.7 min | 624 wps | — | 0.615 GB |
| Qdrant Cloud | DBpedia (1536-dim) | 100K | 3.9 min | 428 wps | 0s (concurrent) | 0.614 GB |
| turbopuffer | H&M (2048-dim) | 105K | 3.1 min | 574 wps | — | 0.873 GB |
| Qdrant Cloud | H&M (2048-dim) | 105K | 9.0 min | 304 wps | 195.8s | 0.926 GB |
| turbopuffer | Multi-tenant 768-dim (100 ns, parallel upload) | 1M | 2.4 min | 6847 wps | — | — |
| Qdrant Cloud | Multi-tenant 768-dim (1 collection, sequential) | 1M | 20.5 min | 816 wps | 5.1s | 3.200 GB |

†Total time = upsert + extra index wait. For Qdrant H&M: 5.8 min upsert + 3.3 min HNSW build = 9.0 min total. For DBpedia: 3.9 min upsert, HNSW finished concurrently (extra wait = 0s), total = 3.9 min.

‡Extra index wait = additional time after last upsert batch until GREEN. DBpedia = 0s (1536-dim HNSW finished within upsert window); H&M = 195.8s (2048-dim spilled past upsert). Same benchmarking code for all datasets.

§Stored GB: tpuf = `billable_logical_bytes_written` (upsert response, f16 + centroid-tree overhead); Qdrant = vectors + payload from `/telemetry?details_level=10` (f32). Despite tpuf using f16, centroid-tree overhead brings storage close to Qdrant's f32 footprint. MT tpuf value not captured in this run.

**Write-time vs query-time tradeoff:** Qdrant builds HNSW for all datasets — 195.8s additional wait for H&M (2048-dim), embedded within the 234s window for DBpedia (1536-dim, builds fast enough to finish concurrently), 5.1s for MT. This one-time cost enables 1.9ms server-side queries. turbopuffer stores raw vectors to S3 (0.615 GB for DBpedia — 1:1 with raw vector size) with no write-time indexing. The deferred cost appears at every query: ~0.615 GB scanned per DBpedia query, so tpuf cost scales with data size × QPS.

Qdrant is slower to upload for H&M (larger vectors, more HTTP payload per batch) and significantly slower for the multi-tenant collection — building per-tenant HNSW sub-graphs (`payload_m=16`) is expensive at write time. turbopuffer writes directly to object storage with no server-side index construction.

---

### Search — DBpedia 100K × 1536-dim (unfiltered, same-region client)

#### Single-connection baseline (p=1) — most reliable measurement

| Engine | RPS | p50 | p99 | Srv p50 | Srv p99 | Billed GB/q | Recall |
|--------|-----|-----|-----|---------|---------|-------------|--------|
| turbopuffer | 57.1 RPS | 15.9ms | 47.1ms | 10ms | 40ms | 0.615 GB | 98.51% |
| Qdrant Cloud | **143.2 RPS** | **6.9ms** | **8.4ms** | **1.9ms** | **2.5ms** | — | 98.36% |

**tpuf scans the full dataset per query:** 0.615 GB billed ≈ entire 0.614 GB dataset. Cost scales directly with data size. Qdrant server p99 is rock-stable at 2.5ms from 1–50 QPS; tpuf server p99 is 40ms (4× above its p50).

**Same recall, 2.5× lower latency and throughput for Qdrant.** This gap is architectural: Qdrant's HNSW index lives in RAM (**1.9ms server-side**, confirmed via `server_time` response header; remaining ~5ms is network RTT). turbopuffer traverses a centroid tree backed by NVMe/S3 — the **~10ms server-side floor** is irreducible regardless of configuration. This 5× server-latency gap (10ms vs 1.9ms) is independent of network distance.

#### Parallel connections (p=8)

| Engine | RPS |
|--------|-----|
| turbopuffer (serverless) | 51.4 RPS |
| Qdrant Cloud | **48.1 RPS** |

At p=8, throughput converges — turbopuffer's serverless autoscaling partially offsets the latency gap under concurrency.

---

### Search — DBpedia — Fixed-QPS Sweep (dollar break-even)

Queries fired at exact rates for 120 seconds each. Latency figures are real measured distributions; costs are based on turbopuffer's published pricing.

| QPS | tpuf p50 | tpuf p99 | tpuf srv_p99 | **tpuf $/mo** | qdrant p50 | qdrant p99 | qdrant srv_p99 | **qdrant $/mo** | Cheaper |
|-----|----------|----------|--------------|--------------|------------|------------|----------------|----------------|---------|
| 1   | 21.4ms | 56.3ms | 46ms | **$3.42** | 7.9ms | 22.2ms | 2.7ms | **$26.10** | tpuf (7.6×) |
| 5   | 15.5ms | 33.8ms | 25ms | **$16.69** | 7.7ms | 14.6ms | 2.5ms | **$26.10** | tpuf (1.6×) |
| 10  | 15.9ms | 41.3ms | 35ms | **$33.28** | 7.4ms | 12.2ms | 2.5ms | **$26.10** | Qdrant (1.3×) |
| 20  | 15.7ms | 44.7ms | 38ms | **$66.46** | 7.6ms | 13.0ms | 2.5ms | **$26.10** | Qdrant (2.5×) |
| 50  | 15.2ms | 42.7ms | 35ms | **$165.99** | 7.3ms | 10.7ms | 2.5ms | **$26.10** | Qdrant (6.4×) |

**Observations:**
- turbopuffer latency is flat at ~15ms across all QPS levels — serverless autoscaling handles the load without queueing at these rates.
- Qdrant server p99 is flat at 2.5ms from 1 to 50 QPS — the node is far from saturated.
- Cost crossover is at **~10 QPS**. At that crossover, Qdrant is already 3× lower p99.
- At 50 QPS: turbopuffer costs **6× more** with **2× worse latency**. There is no operating point where turbopuffer is simultaneously cheaper and faster for a sustained workload.

---

### Search — H&M 105K × 2048-dim (filtered, categorical attribute)

#### turbopuffer (pinned, 4 replicas, p=32 concurrent)

| State | RPS | Mean | p99 | Srv p50 | Srv p99 | Billed GB/q | Recall |
|-------|-----|------|-----|---------|---------|-------------|--------|
| Warm (NVMe-cached) | 6.0 RPS | 167ms | 538ms | 119ms | 472ms | 0.872 GB | **88.94%** |
| **Cold** (fresh namespace, no warmup) | 3.5 RPS | 285ms | **1,891ms** | 149ms | 1,777ms | 0.872 GB | **88.94%** |

**94% of cold p99 is server-side:** server_p99 = 1,777ms out of total_p99 = 1,891ms. The cold-start delay is S3 fetches, not network. Even warm: server_p99 = 472ms out of 538ms (88% server-side NVMe tail).

Recall measured separately at p=1 (500 queries) after warmup. The drop from ~98.5% unfiltered to **88.94% filtered** is architectural: SPFresh runs ANN on the full dataset first, then applies the filter as a post-processing step. When the filter is selective, discarded candidates are not replaced — the returned set can be smaller than top-10, directly hurting recall. Server p50 of 119ms for filtered warm queries confirms the floor is on-server centroid traversal, not network.

Cold-state means the namespace was freshly created via `copy_from` (no NVMe cache). After any replica restart or provisioning event, turbopuffer resets to cold — the first queries must fetch centroid data from S3. Warm p99 is 538ms; cold p99 is 1,891ms (**3.5× worse, same config**).

#### Qdrant Cloud (1 node 2CPU/8GB, p=1)

| State | RPS | p50 | p99 | Server latency | Recall |
|-------|-----|-----|-----|----------------|--------|
| Always warm | **159.4 RPS** | **6.1ms** | **10.1ms** | **1.0ms** | **95.71%** |

Qdrant's HNSW graph is in RAM — there is no cold-start state. Latency and recall are identical regardless of whether the cluster just restarted. Server latency of 1.0ms for filtered queries confirms that Qdrant's payload index adds minimal overhead. The total is still under 11ms p99.

**The key risk for filtered search:** turbopuffer's cold p99 (~1.9s) activates whenever a pinned replica restarts or is newly provisioned. For a SaaS that autoscales or redeploys, this risk is live. Qdrant has no equivalent.

---

### Search — Multi-Tenant (1M × 768-dim, 100 tenants, 10K vectors/tenant)

Dataset: 1M vectors across 100 tenants (~10K per tenant). turbopuffer routes each query to its per-tenant namespace (100 namespaces total). Qdrant uses one collection with per-tenant HNSW sub-graphs (`m=0, payload_m=16, is_tenant=True`).

#### Single-connection (p=1) — reliable measurement

| Engine | Config | RPS | p50 | p99 | Recall |
|--------|--------|-----|-----|-----|--------|
| turbopuffer | ns-per-tenant | 33.5 RPS | 24.0ms | 119.6ms | **100%** |
| Qdrant Cloud | payload_m=16 | **184.6 RPS** | **5.3ms** | **9.7ms** | **100%** |

**Qdrant delivers 5.5× more throughput at 4.5× lower p50 — both engines at 100% recall.**

turbopuffer's p99 (119.6ms vs Qdrant's 9.7ms) is wide because each query requires a separate HTTP connection to a different namespace endpoint. Qdrant's sub-graph routing is in-process. The 24ms p50 vs 5.3ms reflects the same architectural gap as unfiltered search, with additional namespace routing overhead.

#### Concurrency sweep

| Config | p | RPS | p50 | p99 | Srv p99 | Billed GB/q | Recall |
|--------|---|-----|-----|-----|---------|-------------|--------|
| tpuf ns-per-tenant | 1 | 33.5 | 24.0ms | 119.6ms | 114ms | 0.256 GB | 100% |
| tpuf ns-per-tenant | 8 | 43.7 | 21.7ms | 54.9ms | 41ms | 0.256 GB | 100% |
| tpuf ns-per-tenant | 32 | 16.8 | 55.3ms | 207ms | 29ms | 0.256 GB | 100% |
| qdrant payload_m16 | 1 | **184.6** | **5.3ms** | **9.7ms** | — | — | 100% |
| qdrant payload_m16 | 8 | 46.9 | 17.3ms | 96.8ms | — | — | 100% |
| qdrant payload_m16 | 32 | 9.5 | 74.5ms | 444.8ms | — | — | 100% |

At p=32, tpuf's serverless autoscaling (16.8 RPS, 55ms p50) outpaces the single 2CPU Qdrant node (9.5 RPS, 75ms p50) — the node saturates under 32 concurrent queries. This is a sizing issue, not architectural: a larger Qdrant node restores the 5× advantage.

At high concurrency (p=32), both engines saturate — Qdrant's single-node CPU becomes the bottleneck, and turbopuffer's serverless pool handles the parallel namespace requests slightly better. The single-connection (p=1) measurement is the fair comparison for per-query latency.

**The cost question for multi-tenant:** turbopuffer's 100 namespaces cost near-zero when idle. A SaaS with 100 customers and only 5 active at any moment pays for 5 active namespaces' compute. Qdrant's cluster costs $26/month regardless of how many tenants are active. Below ~8 QPS per tenant on average, turbopuffer is cheaper. Above that, Qdrant is cheaper and 5.5× faster.

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
| tpuf pinned 4r (0.43 GB → 64 GB billed) | **$2,476** | 6.0 | 538ms | 88.94% |
| Qdrant Cloud 1 node | **$26.10** | 159.4 | 10.1ms | 95.71% |

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
| Filtered / faceted search (e-commerce) | Risky | ✓ | Cold p99 ~1.9s. Qdrant always 10.1ms. Recall: tpuf 88.94% vs Qdrant 95.71%. |
| Real-time recommendations / consumer apps | — | ✓ | 15.9ms tpuf p50 vs 6.9ms Qdrant. 2.3× gap is user-visible. |
| Precision-sensitive (medical/legal/finance) | — | ✓ | Fixed 88.94–98.51% recall, not tunable. |
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

1. **Latency floor:** 6.9ms p50 vs 15.9ms. HNSW in RAM (**1.9ms server-side**) vs NVMe/S3 centroid traversal (**~10ms server-side floor**). This 5× server-latency gap is independent of network distance and not configurable. Remaining ~5ms in Qdrant's total is network RTT.
2. **Filtered search consistency:** Qdrant payload indexes keep filter latency at ~10ms p99 warm or cold. turbopuffer cold p99 for filtered search is ~1.9s.
3. **Multi-tenant throughput:** Qdrant's `payload_m=16` sub-graph approach delivers 5.5× more throughput at 4.5× lower p50 vs ns-per-tenant, both at 100% recall.
4. **Recall control:** Full ef, quantization, oversampling dial. turbopuffer locked at 88.94% filtered / 98.51% unfiltered — no tuning knobs.
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

---

## Raw Results

Full benchmark state: `results/reproduce-2026-06-22T22-25-07/state.json`
