# turbopuffer vs Qdrant Cloud — Executive Summary v2

**Date:** 2026-06-22 | **Author:** Shivendu Kumar, Qdrant | **Region:** aws-us-west-2  
**Previous:** [turbopuffer-report-simple.md](turbopuffer-report-simple.md) (2026-06-17)

> v2 is a full re-run using `reproduce_comparison.py` — consistent batch=128 across both engines, async client throughout. Previous report used inconsistent batch sizes and a multiprocessing harness that inflated latency. **Key new data:** (1) fixed-QPS cost measurement instead of computed estimates, (2) multi-tenant now shows Qdrant vs turbopuffer head-to-head.

---

## Bottom Line

**Unchanged from v1:** From the same AWS region, Qdrant beats turbopuffer on every performance metric — lower latency, higher throughput, better recall, no cold-start risk. turbopuffer's value is cost-to-zero for idle namespaces.

**What v2 updates:**

- The scary H&M cold p99 (12.7s in v1) was inflated by cross-region RTT compounding with S3. **Same-region cold p99 is ~1.6s** — still unacceptable for user-facing SLAs, but not 12.7s.
- Multi-tenant is now measured: Qdrant with per-tenant HNSW sub-graphs (`payload_m=16`) delivers **5.2× higher throughput** at p=1 vs turbopuffer ns-per-tenant — both at 100% recall.
- The cost break-even was previously estimated. v2 **measures it directly** via a fixed-QPS sweep: crossover is at ~10 QPS sustained, at which point Qdrant is already cheaper ($26/mo vs $33/mo) **and** 2× faster.

---

## Head-to-Head (p=1, same-region, consistent batch=128)

| Dimension | turbopuffer | Qdrant Cloud | Change from v1 |
|-----------|-------------|--------------|----------------|
| Single-query mean latency | 15.6ms | **6.8ms** | Consistent (v1: 16.9ms / 6.3ms) |
| Single-query RPS | 64 RPS | **147 RPS** | +15% both (async client) |
| Single-query p99 | 39.9ms | **11.8ms** | Consistent |
| H&M filtered mean latency | 93ms (warm) | **6.0ms** | v1: 73ms warm; consistent |
| H&M cold p99 | **~1.6s** | **8.8ms** | v1 was 12.7s (cross-region artifact) |
| Multi-tenant RPS (p=1) | 38.6 RPS | **199.5 RPS** | **New data** |
| Multi-tenant latency (p=1) | 19.7ms p50 | **4.9ms p50** | **New data** |
| Recall — unfiltered | 98.4% | 98.4% | Same |
| Recall — multi-tenant (p=1) | 100% | **100%** | **New data** |
| Upload DBpedia 100K, batch=128 | 2.4 min | **3.8 min** | Faster than v1 (async) |
| Upload H&M 105K, batch=128 | 3.0 min | 9.0 min | Faster than v1 (async) |
| Upload multi-tenant 100K | 2.3 min | 20.6 min | **New data** |
| Cold-start risk (filtered) | **~1.6s p99 same-region** | None | Was 12.7s in v1 (cross-region artifact) |
| Cost above ~10 QPS | More expensive | **Cheaper** | Confirmed by measurement |
| Cost below ~8 QPS | **Cheaper** | More expensive | Confirmed by measurement |

---

## Key Numbers

### Upload (batch=128, async client — v2)

| Engine | Dataset | Vectors | Time |
|--------|---------|---------|------|
| turbopuffer | DBpedia (1536-dim) | 100K | **2.4 min** |
| Qdrant Cloud | DBpedia (1536-dim) | 100K | **3.8 min** |
| turbopuffer | H&M (2048-dim) | 105K | **3.0 min** |
| Qdrant Cloud | H&M (2048-dim) | 105K | **9.0 min** |
| turbopuffer | Multi-tenant 768-dim | 100K (100 ns) | **2.3 min** |
| Qdrant Cloud | Multi-tenant 768-dim | 100K (1 collection) | **20.6 min** |

The 2–10× speedup over v1 upload times comes entirely from using an async client (persistent connection pool) instead of the multiprocessing harness (TCP/TLS reconnect per batch). Qdrant improved more in absolute time because it benefited more from connection reuse. The underlying data transfer rates are comparable.

### DBpedia — single query (p=1)

| Engine | RPS | Mean | p50 | p99 | Recall |
|--------|-----|------|-----|-----|--------|
| turbopuffer | 64 | 15.6ms | 14.8ms | 39.9ms | 98.4% |
| Qdrant | **147** | **6.8ms** | **6.5ms** | **11.8ms** | 98.4% |

Same recall, Qdrant 2.3× lower latency and 2.3× more throughput per connection. This gap is architectural — HNSW in RAM (1.9ms server) vs S3-backed centroid traversal (~13–15ms floor). Not closable.

### H&M Filtered — single query (p=1)

| Engine | State | RPS | Mean | p99 | Recall |
|--------|-------|-----|------|-----|--------|
| turbopuffer (pinned 4r) | Warm | ~10.7† | 93ms | 351ms | N/A‡ |
| turbopuffer (pinned 4r) | **Cold** | ~4.8† | 210ms | **1,574ms** | N/A‡ |
| Qdrant | Always warm | **166** | **6.0ms** | **8.8ms** | **95.9%** |

†Concurrent run (p=32); stated RPS = 1/mean, not wall-clock. Actual throughput ≈ 10-15× higher.  
‡Recall unreliable at p>1 (query-to-groundtruth mapping breaks under concurrency).

**What changed from v1:** The cold p99 was 12.7s in v1 (measured from a cross-region client where high RTT compounded with S3 round-trips). Same-region cold p99 is **~1.6s**. Still production-unacceptable for user-facing requests, but the 12.7s figure overcounted the true risk.

Qdrant's H&M performance is unchanged at p=1: 6ms mean, 8.8ms p99 — and consistent regardless of warm/cold because HNSW lives in RAM.

### Multi-Tenant — NEW

Dataset: 100K vectors (768-dim), 100 tenants, ~1K vectors/tenant. turbopuffer routes each query to the correct namespace (100 namespaces). Qdrant routes to per-tenant HNSW sub-graph (`m=0, payload_m=16, is_tenant=True` on payload field).

| Engine | Config | RPS (p=1) | Mean | p99 | Recall |
|--------|--------|-----------|------|-----|--------|
| turbopuffer | ns-per-tenant | 38.6 | 25.9ms | 106.7ms | **100%** |
| Qdrant | payload_m=16 | **199.5** | **5.0ms** | **6.9ms** | **100%** |

**Both achieve 100% recall. Qdrant delivers 5.2× higher throughput at 5.2× lower latency.**

This is new data absent from v1. For multi-tenant search, Qdrant's in-collection sub-graphs outperform turbopuffer's namespace-per-tenant model decisively. The cost question is separate: tpuf namespaces cost zero when idle, which matters if most tenants see sparse traffic.

---

## Cost Crossover — Measured (NEW)

Fixed-QPS sweep on DBpedia 100K × 1536-dim over 120 seconds per level:

| QPS sustained | tpuf $/mo | tpuf p99 | Qdrant $/mo | Qdrant p99 | Cheaper |
|---------------|-----------|----------|-------------|------------|---------|
| 1 | $3.42 | 63.6ms | $26.10 | 16.4ms | **tpuf (7.6×)** |
| 5 | $16.69 | 36.1ms | $26.10 | 13.0ms | **tpuf (1.6×)** |
| **~10** | **$33** | **36ms** | **$26.10** | **11ms** | **break-even** |
| 20 | $66.46 | 43.0ms | $26.10 | 11.0ms | **Qdrant (2.5×)** |
| 50 | $165.99 | 37.1ms | $26.10 | 15.0ms | **Qdrant (6.4×)** |

v1 computed this analytically. v2 confirms it with real query runs. The crossover at ~10 QPS is real — and at that crossover point Qdrant already has 3× lower p99 latency.

**The structural point:** There is no QPS level where turbopuffer is simultaneously cheaper and faster. Below ~8 QPS it is cheaper but slower. Above ~10 QPS it is both slower and more expensive.

---

## What Stayed the Same

- Qdrant's latency advantage is architectural and permanent (~6.8ms vs ~15.6ms at p=1).
- turbopuffer's serverless mode is still better than pinned for unfiltered search — the autoscaling pool handles concurrency better than a single pinned node.
- Fixed ~98.4% recall for unfiltered search; not tunable.
- Cold-state risk is real for filtered search (1.6s same-region p99 vs 8.8ms Qdrant p99).
- Cost break-even is at ~8–10 QPS sustained per namespace.

## What Changed

- H&M cold p99: 12.7s (v1, cross-region) → **~1.6s (v2, same-region)**. Less alarming but still a hard SLA risk.
- Multi-tenant: v1 compared two turbopuffer configs. v2 shows **Qdrant wins 5.2× on throughput and latency** at p=1, both at 100% recall.
- Upload times: all faster (async client). The relative ordering is the same; absolute numbers are now realistic.
- Cost analysis: confirmed by real measurement instead of formula. Crossover confirmed at ~10 QPS.

---

## Workload Fit

| Workload | Fit | Reason |
|----------|-----|--------|
| Multi-tenant SaaS, most tenants idle | ✓ Good | Zero idle cost; performance loss is ~5× vs Qdrant for active tenants |
| Internal / async semantic search | ✓ Good | Latency tolerance high, infrequent queries |
| Dev / staging environments | ✓ Good | Real data, rarely queried |
| **Sustained multi-tenant (>8 QPS/namespace)** | ✗ Poor | **Qdrant cheaper AND 5× faster** |
| E-commerce / filtered search, cold-state risk | ✗ Poor | ~1.6s p99 cold. Consistent warm Qdrant at 8.8ms p99. |
| Real-time recommendations / consumer-facing | ✗ Poor | ~15ms floor vs Qdrant ~6ms; 2.5× latency disadvantage is user-visible |
| Precision-sensitive (medical/legal) | ✗ Poor | Fixed 96–98.4% recall; no tuning knob |

---

## Marketing Angles (v2)

- **"Multi-tenant done right"** — Qdrant's `payload_m=16` sub-graphs deliver 5.2× throughput and 5.2× lower latency vs turbopuffer ns-per-tenant, both at 100% recall. Same-region, same dataset.
- **"Consistent, not sometimes cold"** — turbopuffer filtered p99 jumps to ~1.6s after any replica restart. Qdrant's HNSW stays in RAM: 8.8ms p99 warm or cold, always.
- **"Cheaper when it matters"** — Above 10 QPS/namespace, Qdrant is 2–6× cheaper than turbopuffer **and** 2× lower latency. There's no operating point where tpuf is simultaneously cheap and fast.
- **"No tuning roulette"** — turbopuffer locks recall at ~96–98.4%. Qdrant lets you set ef, quantization, and oversampling — tune up for quality or down for cost.
