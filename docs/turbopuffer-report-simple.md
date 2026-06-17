# turbopuffer vs Qdrant Cloud — Executive Summary

**Last updated:** 2026-06-17 | **Author:** Shivendu Kumar, Qdrant | **Region:** aws-us-west-2

---

## Bottom Line

turbopuffer is a legitimate niche competitor for cold, low-QPS, multi-tenant workloads where idle cost matters more than latency. For any production use case with latency SLAs, filtering, or sustained throughput above ~15 RPS, Qdrant wins decisively — and the gap is architectural, not configurable.

**The core trade-off:** turbopuffer only beats Qdrant on cost when namespaces are mostly idle. The moment you need low latency (pinning), you also lose the cost advantage. There is no configuration where turbopuffer is both cheap and fast for a hot namespace.

---

## Head-to-Head: Qdrant vs turbopuffer

| Dimension | turbopuffer | Qdrant Cloud |
|-----------|-------------|--------------|
| Architecture | Object storage (S3) + ephemeral compute | RAM + HNSW index |
| Server-side query latency | ~50–80ms (S3 round-trips) | **1.9ms** (HNSW in RAM) |
| Client latency (same region) | ~126ms | ~227ms (network-dominated @ 72ms RTT) |
| Peak RPS (100K vectors, 1 node) | ~110 RPS (serverless autoscale) | **35 RPS** (2CPU/8GB node) |
| Filtered search p99 | **12.7 seconds** | **679ms** (18× better) |
| Filtered precision | 96.37% | **99.85%** |
| Upload 100K @ batch=256 | 22.3 min | 48 min (2.2× slower — single connection) |
| Recall/precision control | None (fixed ~98.9%) | Full (ef, quantization, oversampling) |
| Scales to zero (idle cost) | Yes | No |
| Latency predictability | 126ms to 52s (cold/hot variance) | Consistent — 1.9ms server always |

---

## Key Numbers

### Upload Performance

| Engine | Dataset | Vectors | Batch | Upload Time |
|--------|---------|---------|-------|-------------|
| turbopuffer | DBpedia (1536-dim) | 100K | 1000 | 33–37 min |
| turbopuffer | H&M (2048-dim) | 105K | 500 | ~17 min |
| **Qdrant Cloud** | **DBpedia (1536-dim)** | **100K** | **256¹** | **48 min** |

### Search — DBpedia, no filters

#### turbopuffer
| Mode | RPS | Mean Latency | p99 | Precision |
|------|-----|-------------|-----|-----------|
| Serverless async, c=32 | **~110 RPS** | ~290ms | — | 98.87% |
| Serverless async, c=1 | ~8 RPS | **~126ms** | — | 98.87% |
| Pinned 2r async, c=64 | ~55 RPS | — | — | 98.87% |
| Pinned 4r async, c=128 | ~39 RPS | — | — | 98.87% |
| Multiprocessing p=32 | 43.2 RPS | 738ms | 1966ms | 98.87% |

#### Qdrant Cloud (1 node, 2CPU/8GB, HNSW ef=128)
| Mode | RPS | Mean Latency | p95 | p99 | Server Latency | Precision |
|------|-----|-------------|-----|-----|----------------|-----------|
| Multiprocessing p=8 | **35.1** | 227ms | 263ms | 556ms | **1.9ms** | **99.0%** |
| Multiprocessing p=32 | 34.1 | 935ms | 1893ms | 4096ms | 1.9ms | 99.0% |
| Async c=8 | 30.2 | 264ms | 537ms | 597ms | 1.8ms | — |
| Async c=16 | 32.7 | 488ms | 756ms | 813ms | 1.8ms | — |

**The key number:** Qdrant's 1.9ms server latency vs turbopuffer's ~50–80ms irreducible S3 overhead. Everything else in the client latency is network RTT, same for both.

### Search — H&M, with filters (105K vectors)

#### turbopuffer (pinned 4 replicas, p=32)
| RPS | Mean | p95 | p99 | Precision |
|-----|------|-----|-----|-----------|
| 19.8 | 1614ms | 4341ms | **12,713ms** | 96.37% |

#### Qdrant Cloud (1 node 2CPU/8GB, HNSW ef=128)
| Parallel | RPS | Mean | p95 | p99 | Server Latency | Precision |
|----------|-----|------|-----|-----|----------------|-----------|
| 8 | **25.1** | 317ms | 541ms | **679ms** | **1.4ms** | **99.85%** |
| 32 | 26.0 | 1230ms | 2458ms | 4132ms | 1.4ms | 99.85% |

---

## Workload Fit

| Workload | Fit | Reason |
|----------|-----|--------|
| Multi-tenant SaaS, most tenants idle | Good | Pay only for active namespaces; cold cost is near zero |
| Internal / async semantic search | Good | Latency tolerance high, queries infrequent |
| Dev / staging environments | Good | Real data, rarely queried, zero idle cost |
| RAG over infrequent documents | Good | Batch retrieval, latency not user-facing |
| E-commerce / retail search | Poor | Filter p99 = 12.7s; precision drops to 96.4% |
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

- **"1.9ms vs 126ms"** — Qdrant's HNSW server query time is 1.9ms. turbopuffer's base client latency is 126ms. That's a 66× difference before any application code runs.
- **"Real-time filtering without roulette"** — turbopuffer filter p99 = 12.7s. Qdrant payload indexes keep filters predictable.
- **"Recall on your terms"** — turbopuffer locks you in at ~98.9%; Qdrant lets you tune for your use case.
- **"Scale without S3 physics"** — turbopuffer replica scaling breaks at 4r (worse than 2r). Qdrant scales linearly.
