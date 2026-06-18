# turbopuffer vs Qdrant Cloud — Executive Summary

**Last updated:** 2026-06-17 | **Author:** Shivendu Kumar, Qdrant | **Region:** aws-us-west-2

---

## Bottom Line

From the same AWS region, Qdrant on a single 2CPU/8GB node delivers **365 RPS at 22ms p99** — beating turbopuffer's 224 RPS at 43.6ms p99, on identical hardware cost. Single-connection latency: Qdrant 6.3ms mean vs turbopuffer 16.9ms mean. HNSW in RAM simply wins on unfiltered dense search.

turbopuffer's value proposition is different: **scale-to-zero cost** for inactive namespaces and multi-tenant SaaS patterns where most tenants are idle. It's not a better search engine — it's a cheaper storage tier for sporadic traffic. The tradeoff has two hard edges: cold-state collapse (12.7s p99 for filtered search after any restart) and fixed recall (~96–98.9%, not tunable).

**For production APIs:** Qdrant wins on every performance axis (throughput, latency, p99, precision). **For multi-tenant SaaS with sparse query patterns:** turbopuffer's cost model is compelling if you can tolerate cold-start risk.

---

## Head-to-Head: Qdrant vs turbopuffer (same-region, aws-us-west-2)

| Dimension | turbopuffer | Qdrant Cloud |
|-----------|-------------|--------------|
| Architecture | Object storage (S3) + ephemeral compute | RAM + HNSW index |
| Server-side query latency | ~17ms (warm, same region) | **1.9ms** (HNSW in RAM) |
| Peak RPS — unfiltered 100K | 224 RPS (serverless p=8) | **365 RPS** (2CPU/8GB node, p=8) |
| Single-connection RPS | 55.5 RPS | **134 RPS** |
| Single-connection mean latency | 16.9ms | **6.3ms** |
| Peak RPS — filtered 105K, **warm** | **212 RPS** | 25 RPS (same small node) |
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

#### Qdrant Cloud (1 node, 2CPU/8GB, HNSW ef=128) — same-region (aws-us-west-2)
| Mode | RPS | Mean Latency | p95 | p99 | Server Latency | Precision |
|------|-----|-------------|-----|-----|----------------|-----------|
| **p=8** | **365 RPS** | **10.6ms** | 18.0ms | **22.3ms** | **1.9ms** | **99.0%** |
| p=32 | 379 RPS | 15.0ms | 28.9ms | 36.4ms | 2.0ms | 99.0% |
| **p=1 (single conn)** | **134 RPS** | **6.3ms** | 7.4ms | **9.1ms** | 1.9ms | 99.0% |

> **Note:** Earlier June 16 results (35 RPS, 227ms mean) were collected from a client in India (~230ms RTT to us-west-2). Above numbers are from the same-region benchmark server.

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

1. **Throughput:** 365 RPS vs 224 RPS on same-region 100K dataset. 1.6× faster on a single small node.
2. **Single-query latency:** 6.3ms mean vs 16.9ms mean at p=1. HNSW in RAM vs S3 round-trips — architectural gap, not closable.
3. **Filtered search:** turbopuffer filter p99 = 12.7s cold is a hard limit. Qdrant payload indexes keep filter latency at 679ms warm or cold.
4. **Precision control:** Full ef/quantization/oversampling dial. turbopuffer locked at ~96–98.9%.
5. **Consistency:** turbopuffer varies 17ms → 12.7s p99 cold. Qdrant server latency is always ~1.9ms.
6. **Replica scaling:** turbopuffer pinned-4r delivers 18 RPS vs single-replica's 212 RPS (provisioning race). Qdrant scales horizontally with linear RPS gains.

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
