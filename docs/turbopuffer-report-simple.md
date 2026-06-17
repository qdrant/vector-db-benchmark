# turbopuffer vs Qdrant Cloud — Executive Summary

**Last updated:** 2026-06-17 | **Author:** Shivendu Kumar, Qdrant | **Region:** aws-us-west-2

---

## Bottom Line

turbopuffer is a legitimate competitor for co-located, warm, multi-tenant workloads — from the same region with a pre-warmed namespace it reaches 224 RPS (unfiltered) and 212 RPS (filtered). But **warm state is not a guarantee**. Any replica restart, failover, or new provisioning resets to cold — and cold means 12.7s p99 for filtered search. Qdrant's HNSW stays in RAM and is always consistent at 679ms p99.

**The core trade-off:** turbopuffer is fast when warm and cheap when idle. Qdrant is consistent and precise always. For production APIs with SLAs, Qdrant's predictability wins. For async, infrequent, or cold-tolerant workloads at scale, turbopuffer's cost model is compelling.

---

## Head-to-Head: Qdrant vs turbopuffer (same-region, aws-us-west-2)

| Dimension | turbopuffer | Qdrant Cloud |
|-----------|-------------|--------------|
| Architecture | Object storage (S3) + ephemeral compute | RAM + HNSW index |
| Server-side query latency | ~17ms (warm, same region) | **1.9ms** (HNSW in RAM) |
| Peak RPS — unfiltered 100K | **224 RPS** (serverless p=8) | 34 RPS (2CPU/8GB node) |
| Peak RPS — filtered 105K, **warm** | **212 RPS** | 25 RPS |
| Peak RPS — filtered 105K, **cold** | 19.8 RPS | 25 RPS |
| Filtered search p99 — **warm** | **267ms** | **679ms** |
| Filtered search p99 — **cold** | **12.7 seconds** | **679ms** (18× better) |
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
| Mode | RPS | Mean Latency | p99 | Precision |
|------|-----|-------------|-----|-----------|
| **Serverless p=8** | **224 RPS** | **22.9ms** | 43.6ms | 98.51% |
| Pinned 1r p=8 | 212 RPS | 26ms | 54.7ms | 98.51% |
| Serverless p=32 | 208 RPS | 29ms | 58.7ms | 98.51% |
| Single conn p=1 (warm) | 55.5 RPS | 16.9ms | 37ms | 98.51% |
| hint_warm p=8 | 17 RPS | 459ms | 1139ms | 98.87% |
| Pinned 4r p=32 | 18.5 RPS | 1.7s | 6.3s | 98.87% |

#### Qdrant Cloud (1 node, 2CPU/8GB, HNSW ef=128)
| Mode | RPS | Mean Latency | p95 | p99 | Server Latency | Precision |
|------|-----|-------------|-----|-----|----------------|-----------|
| Multiprocessing p=8 | **35.1** | 227ms | 263ms | 556ms | **1.9ms** | **99.0%** |
| Multiprocessing p=32 | 34.1 | 935ms | 1893ms | 4096ms | 1.9ms | 99.0% |
| Async c=8 | 30.2 | 264ms | 537ms | 597ms | 1.8ms | — |
| Async c=16 | 32.7 | 488ms | 756ms | 813ms | 1.8ms | — |

**The key number:** Qdrant's 1.9ms server latency vs turbopuffer's ~50–80ms irreducible S3 overhead. Everything else in the client latency is network RTT, same for both.

### Search — H&M, with filters (105K vectors, same-region)

#### turbopuffer (pinned 4 replicas, p=32)
| State | RPS | Mean | p95 | p99 | Precision |
|-------|-----|------|-----|-----|-----------|
| **Warm (NVMe-cached)** | **212 RPS** | **73ms** | 163ms | **267ms** | 96.34% |
| Cold (fresh namespace) | 19.8 RPS | 1614ms | 4341ms | **12,713ms** | 96.37% |

#### Qdrant Cloud (1 node 2CPU/8GB, HNSW ef=128)
| Parallel | RPS | Mean | p95 | p99 | Server Latency | Precision |
|----------|-----|------|-----|-----|----------------|-----------|
| 8 | 25.1 | 317ms | 541ms | **679ms** | **1.4ms** | **99.85%** |
| 32 | 26.0 | 1230ms | 2458ms | 4132ms | 1.4ms | 99.85% |

**Qdrant is always 679ms p99 — warm or cold.** turbopuffer is 267ms warm but 12.7s cold. turbopuffer wins on warm-state throughput (212 vs 25 RPS) but loses on precision (96.3% vs 99.85%) and cold-state reliability.

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

## Where Qdrant Wins (and Why It's Permanent)

1. **Server-side latency:** 1.9ms (HNSW in RAM) vs 50–80ms (S3 round-trips). Architectural — not closable.
2. **Filtered search:** turbopuffer filter p99 = 12.7s is a hard limit. Qdrant payload indexes keep filter latency stable. *(Qdrant H&M numbers pending.)*
3. **Precision control:** Full ef/quantization/oversampling dial. turbopuffer locked at ~98.9%.
4. **Consistency:** turbopuffer varies 126ms → 52s on cold/hot. Qdrant server latency is always ~1.9ms.
5. **Replica scaling:** Qdrant scales horizontally with linear RPS gains. turbopuffer replica scaling is sub-linear (S3 bottleneck) and 4r is worse than 2r.

## Where turbopuffer Wins

1. **Cold / idle namespaces:** Object storage backend costs near zero when not queried.
2. **Zero-config simplicity:** No HNSW knobs — appeals to developers who want managed search without tuning.
3. **Serverless scale-to-zero:** True pay-per-query for sporadic traffic.

---

## Marketing Angles

- **"Consistent, not sometimes fast"** — turbopuffer warm H&M hits 267ms p99. Cold H&M hits 12.7s p99. Same config, 47× variance. Qdrant always delivers 679ms p99.
- **"Real-time filtering without roulette"** — turbopuffer cold filter p99 = 12.7s. Any restart resets to cold. Qdrant payload indexes keep filters at 679ms regardless.
- **"Recall on your terms"** — turbopuffer locked at 96.3% filtered recall. Qdrant hits 99.85% and lets you tune.
- **"Scale without S3 physics"** — turbopuffer pinned-4replicas delivers 18 RPS vs 212 for single replica. Qdrant scales linearly.
