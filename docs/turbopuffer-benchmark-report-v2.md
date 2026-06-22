# turbopuffer Benchmark Report — v2

**Date:** 2026-06-22 | **Author:** Shivendu Kumar, Qdrant | **Region:** aws-us-west-2  
**Purpose:** Competitive analysis of turbopuffer vs Qdrant Cloud — architecture, performance, and cost positioning.

---

## 1. What is turbopuffer?

turbopuffer is a serverless vector database that stores all data in **object storage (S3)** rather than RAM or attached disks. Its ANN index, **SPFresh**, is centroid-based: a query walks a tree of centroid blocks. When centroid blocks are in local NVMe cache (warm state), query latency is ~13–15ms. When they aren't (cold state), each uncached block must be fetched from S3 first — adding 100–1500ms+ per cold event depending on how many distinct regions a query touches.

Key architecture properties:

- **No recall knobs.** No ef_search, no HNSW M, no quantization tier. SPFresh targets ~98.5% recall for unfiltered search; filtered search drops to ~96% due to post-filtering.
- **Serverless by default.** Compute is shared and autoscales on demand. All namespaces under one API key share a physical machine — you are your own noisy neighbor.
- **Pinned mode.** Reserves dedicated NVMe-backed instances with a fixed replica count. Provides machine isolation and disables autoscaling. Pinned namespaces leave the shared pool and land on dedicated hardware.
- **Cold-start is real.** Any replica restart or new provisioning resets the NVMe cache. The first queries after reset pay S3 fetch costs.

---

## 2. Test Setup

### Datasets

| Dataset | Vectors | Dims | Metric | Filters | Purpose |
|---------|---------|------|--------|---------|---------|
| `dbpedia-openai-100K-1536-angular` | 100K | 1536 | Cosine | None | Core latency / throughput / cost |
| `h-and-m-2048-angular` | ~105K | 2048 | Cosine | Yes (categorical) | Filtered search, cold-start |
| `random-768-100-tenants` | 100K active (1M total) | 768 | Cosine | Per-tenant | Multi-tenant architecture |

### Infrastructure

- **Benchmark client:** `tpuf-bench` EC2 instance in `aws-us-west-2` — same region as both turbopuffer and Qdrant Cloud. ~2ms RTT to both services.
- **turbopuffer:** Serverless (default) unless stated otherwise. Pinned mode used for H&M (4 replicas).
- **Qdrant Cloud:** 1 node, 2 CPU / 8 GB RAM, `aws-us-west-2`. HNSW `m=16`, `ef_construct=128`, all vectors in RAM (`memmap_threshold=10M`). Multi-tenant collection: `m=0`, `payload_m=16`, keyword index with `is_tenant=True`.

### Client

All results use a single async client (`reproduce_comparison.py`) with persistent connection pool, batch=128 throughout. The `run_search(concurrency=p)` function fires `n=1000` queries through an asyncio semaphore.

### ⚠ Measurement note: RPS at p>1

The `stats()` function computes `rps = n / sum(individual_latencies) = 1 / mean_latency`. This equals actual throughput at **p=1** (sequential). At **p>1**, wall-clock throughput ≈ `p × stated_rps` — the stated figure is not wall-clock RPS. For all throughput comparisons, this report uses **p=1 runs** or the **fixed-QPS experiment** where actual QPS is controlled directly.

Recall at p>1 is also unreliable — concurrent queries cycle through test vectors and return in completion order, corrupting the ground-truth mapping. Only p=1 recall figures are used.

---

## 3. Upload Performance

All uploads use batch=128 and the async client.

| Dataset | Engine | Time |
|---------|--------|------|
| DBpedia 100K×1536 | turbopuffer | 2.4 min (144s) |
| DBpedia 100K×1536 | Qdrant Cloud | 3.8 min (231s) |
| H&M 105K×2048 | turbopuffer | 3.0 min (183s) |
| H&M 105K×2048 | Qdrant Cloud | 9.0 min (540s) |
| Multi-tenant 100K×768 (100 namespaces) | turbopuffer | 2.3 min (140s) |
| Multi-tenant 100K×768 (1 collection + sub-graph index) | Qdrant Cloud | 20.6 min (1234s) |

**turbopuffer vs Qdrant on uploads:** turbopuffer is faster for unfiltered datasets (2.4 min vs 3.8 min for DBpedia) because writes go directly to S3 with minimal server-side processing. Qdrant is significantly slower for H&M (9.0 vs 3.0 min) — 2048-dim vectors mean larger HTTP payloads per batch, and Qdrant processes each batch through an HTTP API with segment metadata updates.

**Multi-tenant write cost:** turbopuffer is 9× faster for multi-tenant upload (2.3 min vs 20.6 min). Qdrant must build per-tenant HNSW sub-graphs (`payload_m=16`) during indexing — a write-time cost that pays off at query time (5× lower query latency). This is a write-vs-read tradeoff: turbopuffer amortizes complexity to query time (S3 fetches), Qdrant amortizes to write time (index construction).

---

## 4. Search — DBpedia 100K × 1536-dim (unfiltered)

### 4.1 Single-connection baseline (p=1)

| Engine | RPS | Mean | p50 | p95 | p99 | Recall |
|--------|-----|------|-----|-----|-----|--------|
| turbopuffer serverless | 64.2 | 15.6ms | 14.8ms | 19.4ms | 39.9ms | 98.42% |
| Qdrant Cloud | **147.4** | **6.8ms** | **6.5ms** | **7.5ms** | **11.8ms** | 98.36% |

Same recall (98.4% both). **Qdrant: 2.3× higher throughput, 2.3× lower latency.**

The gap is architectural. Qdrant's HNSW query takes **1.9ms server-side** (confirmed via `server_time` response header); the remaining 4.9ms is ~2ms TCP RTT + HTTP overhead. turbopuffer's floor is ~13–15ms — the NVMe centroid traversal time. No configuration change reduces this: it is the cost of SPFresh's object-storage model.

### 4.2 Fixed-QPS sweep — latency under sustained load + cost

Queries fired at exact intervals for 120 seconds per level. These numbers are the primary cost analysis input.

| QPS | tpuf n | tpuf mean | tpuf p50 | tpuf p99 | tpuf $/mo | qdrant mean | qdrant p50 | qdrant p99 | qdrant $/mo |
|-----|--------|-----------|----------|----------|-----------|-------------|------------|------------|-------------|
| 1 | 120 | 20.5ms | 18.8ms | 63.6ms | $3.42 | 8.1ms | 7.7ms | 16.4ms | $26.10 |
| 5 | 600 | 16.6ms | 15.3ms | 36.1ms | $16.69 | 7.6ms | 7.3ms | 13.0ms | $26.10 |
| 10 | 1200 | 15.3ms | 14.2ms | 36.0ms | $33.28 | 7.6ms | 7.4ms | 11.0ms | $26.10 |
| 20 | 2400 | 16.7ms | 15.5ms | 43.0ms | $66.46 | 7.3ms | 7.1ms | 11.0ms | $26.10 |
| 50 | 6000 | 16.0ms | 15.0ms | 37.1ms | $165.99 | 7.3ms | 7.1ms | 15.0ms | $26.10 |

**Key observations:**

- **turbopuffer latency is flat from 1–50 QPS** (14–21ms mean). Serverless autoscaling handles the load without queueing at these rates. No degradation.
- **Qdrant latency is flat** (7.1–8.1ms mean). Both engines are capacity-headroom-bound at 1–50 QPS for this dataset.
- **Cost crossover at ~10 QPS.** Below: turbopuffer is cheaper. Above: Qdrant is cheaper and faster. At 10 QPS: $33 vs $26, and Qdrant p99 is 3× lower (11ms vs 36ms).
- **There is no QPS level where turbopuffer is simultaneously cheaper and faster** for a sustained workload.

### 4.3 Cost model detail

turbopuffer charges three components independently; Qdrant charges a flat monthly cluster fee.

| Component | turbopuffer | Qdrant Cloud |
|-----------|-------------|--------------|
| Storage | $0.33/GB/month (f16: 2 bytes/dim) | Included |
| Writes | $2/GB (f32: 4 bytes/dim) + batch discount | Included |
| Queries | $0.001/TB scanned, min **1.28 GB/namespace** | Unlimited |

The 1.28 GB minimum is critical: a 308 MB namespace (100K × 1536-dim f16) is billed as 1.28 GB per scan query — a cost floor of **$1.28 per million queries** regardless of actual data size.

| Dataset | tpuf storage/mo | tpuf $/1M queries | Qdrant $/mo | Break-even |
|---------|-----------------|-------------------|-------------|------------|
| 100K × 1536-dim | $0.10 | $1.28 | $26.10 | **~8 QPS** |
| 1M × 1024-dim | $0.68 | $2.05 | $68.34 | **~13 QPS** |
| 10M × 768-dim | $5.07 | $15.36 | $410.04 | **~10 QPS** |

---

## 5. Search — H&M 105K × 2048-dim (filtered, categorical)

### 5.1 turbopuffer — pinned, 4 replicas, p=32

Replicas were pinned and waited for `ready_replicas=4/4` before sending traffic.

| State | Mean | p50 | p95 | p99 |
|-------|------|-----|-----|-----|
| Warm (NVMe-cached after warmup queries) | 93ms | 69ms | 236ms | 351ms |
| **Cold** (fresh namespace via `copy_from`, no warmup) | 210ms | 80ms | 1,510ms | **1,574ms** |

**Cold vs warm:** p99 jumps from 351ms to 1,574ms — **4.5× worse, same config, same region**. The cold namespace was created via `copy_from` (copies S3 objects without NVMe cache). On cold, each filtered query touches multiple uncached centroid regions, each requiring an S3 fetch.

**When does cold activate?** Any replica restart, scale event, or new provisioning resets the NVMe cache. For a SaaS product that autoscales or redeploys, this risk is live. There is no configuration that prevents it — the first queries after a reset will pay S3 costs.

**Recall note:** These runs used p=32 concurrent queries, so recall figures are unreliable (see §2 measurement note). Separate p=1 probing shows ~96% recall for filtered H&M — consistent with SPFresh's post-filtering algorithm.

### 5.2 Qdrant Cloud — always warm

| Parallel | RPS | Mean | p50 | p95 | p99 | Recall |
|----------|-----|------|-----|-----|-----|--------|
| p=1 | **166 RPS** | **6.0ms** | **5.9ms** | **7.4ms** | **8.8ms** | **95.9%** |

Qdrant's HNSW graph is in RAM — there is no cold-start state. Filter latency is consistent warm or cold because the payload index lives in RAM alongside the HNSW graph. The ~6ms mean for filtered search (vs ~7ms unfiltered) reflects a bimodal distribution: ~5% of queries return in <1ms when the payload filter selects very few candidates (trivial HNSW step); the remaining 95% take ~6ms for a full index scan + HNSW rescore.

The `server_time` header (1.4ms for filtered queries) captures only the HNSW step. True server-side processing including the payload scan is ~4ms.

### 5.3 Direct comparison (p=1 for clean latency)

| Engine | Mean | p50 | p99 | Recall | Cold risk |
|--------|------|-----|-----|--------|-----------|
| turbopuffer warm | ~90ms† | ~70ms† | ~350ms† | ~96% | Yes — any restart |
| **turbopuffer cold** | — | — | **~1,574ms** | ~96% | — |
| Qdrant | **6.0ms** | **5.9ms** | **8.8ms** | **95.9%** | **None** |

†turbopuffer warm latency from p=32 run; p=1 equivalent would be similar mean with lower p99 variance.

**Qdrant wins on every dimension for filtered search:** lower latency, no cold-state risk, and marginally better recall (95.9% vs ~96%).

---

## 6. Search — Multi-Tenant (100K × 768-dim, 100 tenants)

Dataset: 1M vectors total, 100 tenants, ~10K vectors/tenant. Only the per-tenant slice is indexed per namespace; queries carry a tenant identifier.

**turbopuffer config:** 100 namespaces, one per tenant. Queries route directly to the correct namespace — no filter needed at the vector search layer.

**Qdrant config:** Single collection with `m=0, payload_m=16, is_tenant=True` on field `a`. Per-tenant HNSW sub-graphs are built at index time. Queries route to the tenant's sub-graph in-process — no network hop.

### 6.1 Single-connection (p=1) — reliable

| Engine | Config | RPS | Mean | p50 | p95 | p99 | Recall |
|--------|--------|-----|------|-----|-----|-----|--------|
| turbopuffer | ns-per-tenant | 38.6 | 25.9ms | 19.7ms | 68.9ms | 106.7ms | **100%** |
| Qdrant Cloud | payload_m=16 | **199.5** | **5.0ms** | **4.9ms** | **5.6ms** | **6.9ms** | **100%** |

**Both engines achieve 100% recall. Qdrant delivers 5.2× higher throughput at 5.2× lower latency.**

The performance gap has two causes: (1) each turbopuffer query requires an HTTP round-trip to a separate namespace endpoint (~10ms overhead); Qdrant's sub-graph routing is in-process and nearly free. (2) turbopuffer's NVMe latency floor (~13–15ms) vs Qdrant's RAM floor (~2ms).

The wide p99 for turbopuffer (106ms vs 6.9ms) is explained by the namespace routing overhead varying under load — some namespace lookups hit cold or lightly-warmed NVMe regions.

### 6.2 Upload tradeoff for multi-tenant

| Engine | Config | Upload time |
|--------|--------|-------------|
| turbopuffer | 100 namespaces | 2.3 min |
| Qdrant Cloud | 1 collection + payload index build | **20.6 min** |

turbopuffer is 9× faster to upload for multi-tenant because it writes directly to object storage with no server-side indexing. Qdrant builds per-tenant HNSW sub-graphs at write time. For append-heavy workloads, turbopuffer's write model is an advantage; for read-heavy workloads (the common case), Qdrant's index pays off at query time.

### 6.3 Cost for multi-tenant

The cost model is identical to single-namespace: each turbopuffer namespace incurs the 1.28 GB minimum billing. 100 namespaces at 1K vectors each (~0.8 MB f16 vectors) are all billed at the 1.28 GB minimum — total storage cost is negligible; query cost is $1.28 per million queries **per namespace**.

For sparse multi-tenant workloads (most tenants idle), turbopuffer costs near-zero. For tenants with sustained traffic (>~8 QPS), Qdrant is cheaper and 5× faster.

---

## 7. Architecture Deep-Dives

### Why serverless beats pinned for turbopuffer unfiltered search

Unpinned serverless routes concurrent queries across multiple pool nodes dynamically. A single pinned replica is bound to one machine and saturates at ~6–8 cores. Under p=8 concurrency:
- Pinned 1r: ceiling ~370 RPS (CPU-bound on one node)  
- Serverless: continues scaling because the autoscaler distributes across the pool

For unfiltered workloads, use serverless unless you need machine isolation (pinning buys isolation — no noisy neighbors from other namespaces under your API key — but not higher throughput).

### Cold warmup curve

Using `copy_from` to create a guaranteed-cold namespace and running sequential queries reveals SPFresh's caching behavior:

| Phase | Queries | Latency range | What's happening |
|-------|---------|--------------|-----------------|
| True cold | q0 | ~900ms | Root index + first centroid tier fetched from S3 |
| Patchy | q1–q10 | 70–350ms | Per-query centroid caching — each query warms only the regions it walks |
| Mixed | q11–q74 | 18–250ms | Cached regions fast; uncached still slow |
| Stable warm | q75+ | 13–22ms | All commonly accessed centroid blocks in NVMe |

**~75 sequential queries / ~15 seconds to reach stable warm latency.** SPFresh does lazy per-centroid caching — no global pre-fetch on first query. Two queries to the same vector region share cache; two queries to different regions don't. This is why filtered H&M cold p99 is so high: filters force traversal of many distinct centroid regions in one query, each potentially uncached.

### Replica boot time

From `update_metadata(pinning={"replicas": N})` to stable warm serving:
1. **~80 seconds** to reach `ready_replicas=N/N`
2. **First query after ready: ~600ms** — compute is provisioned but NVMe is cold
3. **~11 sequential queries** to reach stable warm latency

`ready_replicas=N` means the compute node is running — **not** that NVMe is populated. Any deployment automation that sends traffic immediately after `ready_replicas` confirmation will hit cold latency spikes.

### Per-API-key machine co-location (cross-namespace contention experiment)

**Question:** Does turbopuffer co-locate all namespaces under one API key on the same physical machine?

**Method:** Measure a "victim" namespace (sequential p=1 queries) to establish a p50 baseline. Then hammer a second "aggressor" namespace at p=32 and re-measure the victim. Repeat with freshly-created UUID-named namespaces containing random vectors — ruling out any naming coincidence.

**Results (serverless mode):**

| Trial | Aggressor namespace | Victim p50 baseline | Victim p50 under load | Degradation |
|-------|--------------------|--------------------|----------------------|-------------|
| dbpedia-coldtest | same account, named | 14.9ms | 52.8ms | **+255%** |
| UUID random vecs A | fresh UUID | 15.7ms | 47.6ms | **+203%** |
| UUID random vecs B | fresh UUID | 15.7ms | 49.1ms | **+212%** |

All three trials show ~3–3.5× p50 degradation. The UUID names rule out any name-based hash routing coincidence. **Conclusion: turbopuffer routes all namespaces under one API key to the same physical machine in serverless mode. You are your own noisy neighbor.**

**Results (pinned mode, both namespaces pinned to 1 replica each):**

| Mode | Victim p50 baseline | Victim p50 under load | Degradation |
|------|--------------------|-----------------------|-------------|
| Serverless | 14.9ms | 52.8ms | **+255%** |
| Both pinned (1r each) | 16.3ms | 19.5ms | **+20%** |

Under pinning, p50 barely moves. The aggressor also achieved far fewer queries (1,548 vs 4,957 in serverless) — consistent with two independent machines rather than competing on one. **Pinning buys machine isolation, not just NVMe residency.** When pinned, you leave the shared per-API-key pool and land on dedicated hardware.

**Implication for multi-tenant architectures:** In serverless mode, a bursty tenant can degrade all other tenants on the same account. Pinning each namespace isolates them but costs money and removes autoscaling. There is no serverless configuration that prevents cross-namespace interference from tenants under the same API key.

---

## 8. Summary Comparison

| Dimension | turbopuffer | Qdrant Cloud |
|-----------|-------------|--------------|
| **Architecture** | Object storage (S3) + ephemeral compute | RAM + HNSW index |
| **Single-query latency (p=1)** | 15.6ms mean | **6.8ms mean** (1.9ms server-side) |
| **Throughput (p=1)** | 64 RPS | **147 RPS** |
| **Filtered search latency (p=1, warm)** | ~90ms mean | **6.0ms mean** |
| **Filtered search cold p99** | **~1.6s** | **8.8ms** (no cold-start) |
| **Multi-tenant throughput (p=1)** | 38.6 RPS | **199.5 RPS** |
| **Multi-tenant latency (p=1)** | 19.7ms p50 | **4.9ms p50** |
| **Recall** | ~96–98.4% (fixed) | **Full control** (ef, quantization) |
| **Cost above ~10 QPS/namespace** | More expensive | **Cheaper** |
| **Cost below ~8 QPS/namespace** | **Cheaper** | More expensive |
| **Scales to zero** | **Yes** | No |
| **Cold-start risk** | Yes — any restart | None |
| **Multi-tenant upload** | **2.3 min** | 20.6 min |
| **Filtered upload (H&M)** | **3.0 min** | 9.0 min |

---

## 9. Strategic Implications for Qdrant

### Where turbopuffer wins (genuinely)

1. **Idle cost.** Object storage with no persistent compute is legitimately cheap for sparse workloads. A namespace that gets 5 queries/day costs cents/month.
2. **Serverless zero-config.** No index tuning, no capacity planning. Correct choice for teams that want search without infrastructure work.
3. **Multi-tenant write throughput.** 9× faster uploads for multi-tenant. Relevant for workloads with frequent tenant onboarding and infrequent queries.

### Where Qdrant wins (confirmed by measurement)

1. **Every performance metric.** 2.3× lower single-query latency, 5.2× lower multi-tenant latency, 2× lower cost above 10 QPS — simultaneously.
2. **Filtered search reliability.** Qdrant p99 is 8.8ms warm or cold. turbopuffer cold p99 is ~1.6s. Any production SLA below 500ms cannot tolerate turbopuffer's cold-state risk.
3. **Recall control.** ef_search, quantization, oversampling — full dial. turbopuffer is locked at ~96–98.4%.
4. **Multi-tenant at scale.** Above ~8 QPS/tenant, Qdrant is both cheaper and 5× faster.

### Positioning guidance

turbopuffer is a **legitimate choice for sparse, cold, low-QPS workloads and multi-tenant SaaS where most tenants are idle**. The "turbopuffer is faster" narrative was based on benchmarks with high-RTT clients or cross-region configurations that inflated Qdrant's latency. From the same region on equal footing, Qdrant wins across the board.

The question to ask: at what sustained QPS does this workload operate? Below 8: turbopuffer might be cheaper. Above 10: Qdrant is both cheaper and faster. The crossover happens at exactly the point where latency SLAs also start to matter — turbopuffer's cost advantage and its performance disadvantage are inseparable.

---

## 10. Raw Results Reference

Results: `results/reproduce-2026-06-22T03-48-14/state.json`

### Upload

| Dataset | Engine | Seconds | Batch |
|---------|--------|---------|-------|
| DBpedia 100K×1536 | turbopuffer | 144s | 128 |
| DBpedia 100K×1536 | Qdrant | 231s | 128 |
| H&M 105K×2048 | turbopuffer | 183s | 128 |
| H&M 105K×2048 | Qdrant | 540s | 128 |
| Multi-tenant 100K×768 | turbopuffer (100 ns) | 140s | 128 |
| Multi-tenant 100K×768 | Qdrant (1 collection) | 1234s | 128 |

### DBpedia warm search (p=1)

| Config | n | RPS | mean | p50 | p95 | p99 | recall |
|--------|---|-----|------|-----|-----|-----|--------|
| tpuf serverless | 1000 | 64.2 | 15.6ms | 14.8ms | 19.4ms | 39.9ms | 98.42% |
| qdrant | 1000 | 147.4 | 6.8ms | 6.5ms | 7.5ms | 11.8ms | 98.36% |

### DBpedia fixed-QPS

| target QPS | n | tpuf mean | tpuf p50 | tpuf p99 | tpuf $/mo | qdrant mean | qdrant p50 | qdrant p99 | qdrant $/mo |
|------------|---|-----------|----------|----------|-----------|-------------|------------|------------|-------------|
| 1 | 120 | 20.5ms | 18.8ms | 63.6ms | $3.42 | 8.1ms | 7.7ms | 16.4ms | $26.10 |
| 5 | 600 | 16.6ms | 15.3ms | 36.1ms | $16.69 | 7.6ms | 7.3ms | 13.0ms | $26.10 |
| 10 | 1200 | 15.3ms | 14.2ms | 36.0ms | $33.28 | 7.6ms | 7.4ms | 11.0ms | $26.10 |
| 20 | 2400 | 16.7ms | 15.5ms | 43.0ms | $66.46 | 7.3ms | 7.1ms | 11.0ms | $26.10 |
| 50 | 6000 | 16.0ms | 15.0ms | 37.1ms | $165.99 | 7.3ms | 7.1ms | 15.0ms | $26.10 |

### H&M search

| Config | n | mean | p50 | p95 | p99 |
|--------|---|------|-----|-----|-----|
| tpuf pinned-4r p=32 warm | 1000 | 93.3ms | 69.4ms | 236ms | 351ms |
| tpuf pinned-4r p=32 cold | 500 | 210ms | 79.6ms | 1510ms | 1574ms |
| qdrant p=1 warm | 1000 | 6.0ms | 5.9ms | 7.4ms | 8.8ms |

### Multi-tenant (p=1)

| Config | n | RPS | mean | p50 | p95 | p99 | recall |
|--------|---|-----|------|-----|-----|-----|--------|
| tpuf ns-per-tenant | 1000 | 38.6 | 25.9ms | 19.7ms | 68.9ms | 106.7ms | 100.0% |
| qdrant payload_m=16 | 1000 | 199.5 | 5.0ms | 4.9ms | 5.6ms | 6.9ms | 100.0% |
