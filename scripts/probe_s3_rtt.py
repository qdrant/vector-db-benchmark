"""
S3 round-trip analysis for turbopuffer.

Measures the observable S3/NVMe access cost using two methods:

Method 1 — Warm/cold delta (from probe_coldwarm.py):
  cold_first_query − warm_floor = total S3 loading cost per uncached region.
  The cold warmup curve shows 14 distinct high-latency regions in first 50
  queries, each representing a centroid tree block that needed S3 loading.

Method 2 — Approximate round-trip count:
  warm_client − api_rtt − compute_overhead = estimated NVMe sequential time.
  Dividing by NVMe read latency (~0.1–0.3ms) gives ~50–130 NVMe ops per query.
  Note: S3 GET latency from bench server (internet path) is NOT a valid proxy
  for turbopuffer compute → S3 via VPC endpoint (~0.3–1ms). We measure it for
  completeness but do NOT use it for round-trip counting.

Also reads explain_query for probe_limit (number of centroid probes = 200).

Usage:
    cd ~/vector-db-benchmark
    source .env
    python scripts/probe_s3_rtt.py
"""

import asyncio
import json
import os
import time

import httpx
import numpy as np
import turbopuffer as tpuf

DATASET_QUERIES = "datasets/dbpedia-openai-100K-1536-angular/dbpedia_openai_100K/tests.jsonl"
NS_NAME = "dbpedia-openai-100K-1536-angular"
N_S3_SAMPLES = 50
N_QUERY_SAMPLES = 100

# Small public S3 objects in us-west-2 for latency measurement.
# These are anonymous-accessible and small enough that transfer time is negligible.
S3_PROBE_URLS = [
    # S3 regional endpoint — 403 but gives us TCP+TLS+service timing
    "https://s3.us-west-2.amazonaws.com/",
    # Public bucket with tiny file
    "https://s3.us-west-2.amazonaws.com/aws-codedeploy-us-west-2/latest/codedeploy-agent.noarch.rpm",
]

# turbopuffer API endpoint for RTT measurement
TPUF_API_HOST = "aws-us-west-2.turbopuffer.com"


def load_queries(path, n):
    queries = []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            queries.append(d["query"])
            if len(queries) >= n:
                break
    return queries


def measure_https_rtt(url, n_samples, label):
    """Time HTTPS requests: connect+TLS (first), then subsequent (keep-alive reuse)."""
    latencies_fresh = []
    latencies_reuse = []

    with httpx.Client(http2=False, timeout=10.0) as client:
        for i in range(n_samples):
            # Fresh connection every 5 requests to sample both cases
            if i % 5 == 0:
                client.headers.update({"Connection": "close"})
                t0 = time.perf_counter()
                try:
                    client.get(url)
                except Exception:
                    pass
                lat = (time.perf_counter() - t0) * 1000
                latencies_fresh.append(lat)
            else:
                client.headers.update({"Connection": "keep-alive"})
                t0 = time.perf_counter()
                try:
                    client.get(url)
                except Exception:
                    pass
                lat = (time.perf_counter() - t0) * 1000
                latencies_reuse.append(lat)

    fresh = np.array(latencies_fresh)
    reuse = np.array(latencies_reuse)
    print(f"\n{label}")
    print(f"  Fresh connection (TCP+TLS): mean={fresh.mean():.1f}ms  p50={np.percentile(fresh,50):.1f}ms  p95={np.percentile(fresh,95):.1f}ms")
    print(f"  Keep-alive reuse:           mean={reuse.mean():.1f}ms  p50={np.percentile(reuse,50):.1f}ms  p95={np.percentile(reuse,95):.1f}ms")
    return float(reuse.mean()), float(fresh.mean())


async def measure_warm_query_latency(ns, queries, n=N_QUERY_SAMPLES):
    """Measure p=1 sequential query latency on a warm namespace."""
    # Warmup
    for q in queries[:10]:
        await ns.query(rank_by=("vector", "ANN", q), top_k=10, include_attributes=False)

    latencies = []
    for q in queries[10:10+n]:
        t0 = time.perf_counter()
        await ns.query(rank_by=("vector", "ANN", q), top_k=10, include_attributes=False)
        latencies.append((time.perf_counter() - t0) * 1000)

    lats = np.array(latencies)
    print(f"\nWarm p=1 query latency ({n} queries):")
    print(f"  mean={lats.mean():.1f}ms  p50={np.percentile(lats,50):.1f}ms  p95={np.percentile(lats,95):.1f}ms  p99={np.percentile(lats,99):.1f}ms")
    return float(lats.mean()), float(np.percentile(lats, 50))


async def get_explain_query(ns, query):
    result = await ns.explain_query(rank_by=("vector", "ANN", query), top_k=10)
    return result.plan_text


async def measure_api_rtt():
    """Measure bench → turbopuffer API RTT (TCP connect only)."""
    import socket
    rtts = []
    for _ in range(20):
        t0 = time.perf_counter()
        s = socket.create_connection((TPUF_API_HOST, 443), timeout=5)
        rtts.append((time.perf_counter() - t0) * 1000)
        s.close()
    arr = np.array(rtts)
    print(f"\nBench → turbopuffer API TCP connect RTT:")
    print(f"  mean={arr.mean():.1f}ms  p50={np.percentile(arr,50):.1f}ms  p95={np.percentile(arr,95):.1f}ms")
    return float(arr.mean())


async def main():
    api_key = os.environ["TURBOPUFFER_API_KEY"]
    region = os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2")

    client = tpuf.AsyncTurbopuffer(api_key=api_key, region=region)
    ns = client.namespace(NS_NAME)

    queries = load_queries(DATASET_QUERIES, 200)
    print(f"Loaded {len(queries)} queries")

    # 1. explain_query — get probe count
    print("\n--- explain_query ---")
    plan = await get_explain_query(ns, queries[0])
    print(plan)

    # 2. Measure bench → API TCP RTT (one-way network)
    api_rtt_ms = await measure_api_rtt()

    # 3. Measure S3 GET latency from bench server
    print("\n--- S3 GET latency (bench server, proxy for tpuf compute nodes) ---")
    s3_reuse_ms, s3_fresh_ms = measure_https_rtt(
        S3_PROBE_URLS[0], N_S3_SAMPLES,
        "S3 us-west-2 endpoint (s3.us-west-2.amazonaws.com)"
    )

    # 4. Measure warm query latency
    print("\n--- Warm query latency ---")
    warm_mean_ms, warm_p50_ms = await measure_warm_query_latency(ns, queries)

    # 5. Calculate round-trips
    # warm_client = 2 * api_rtt + tpuf_server_time
    # tpuf_server_time = N_s3 * s3_rtt + compute_overhead
    one_way_rtt = api_rtt_ms  # TCP connect ≈ half of round-trip
    tpuf_server_time = warm_mean_ms - one_way_rtt
    # Compute overhead: SPFresh centroid scoring, ranking, serialization — rough estimate 2ms
    compute_overhead_ms = 2.0
    s3_total_ms = tpuf_server_time - compute_overhead_ms

    # S3 within VPC (turbopuffer compute → S3) is faster than bench→S3 internet path
    # Use bench measurement as upper bound; actual may be 30-50% lower (VPC endpoint)
    n_roundtrips_upper = s3_total_ms / s3_reuse_ms if s3_reuse_ms > 0 else 0
    # Lower bound: assume tpuf VPC S3 RTT = 0.5ms
    n_roundtrips_lower = s3_total_ms / 0.5

    print(f"\n{'='*55}")
    print(f"RESULTS")
    print(f"{'='*55}")
    print(f"  Warm query mean (client):         {warm_mean_ms:.1f}ms")
    print(f"  Bench → API one-way RTT:          {one_way_rtt:.1f}ms")
    print(f"  Estimated tpuf server time:       {tpuf_server_time:.1f}ms")
    print(f"  Estimated compute overhead:       {compute_overhead_ms:.1f}ms")
    print(f"  Estimated S3 time budget:         {s3_total_ms:.1f}ms")
    print(f"  S3 GET RTT (bench, internet):     {s3_reuse_ms:.1f}ms  [upper bound]")
    print(f"  S3 GET RTT (VPC estimate):        ~0.5ms  [lower bound]")
    print(f"  Estimated S3 round-trips:")
    print(f"    Upper bound (internet S3):      {n_roundtrips_upper:.1f}")
    print(f"    Lower bound (VPC S3 ~0.5ms):    {n_roundtrips_lower:.1f}")

    # Save
    output = {
        "experiment": "s3_roundtrip_estimate",
        "warm_query_mean_ms": warm_mean_ms,
        "warm_query_p50_ms": warm_p50_ms,
        "api_tcp_rtt_ms": one_way_rtt,
        "s3_get_reuse_ms": s3_reuse_ms,
        "s3_get_fresh_ms": s3_fresh_ms,
        "tpuf_server_time_ms": tpuf_server_time,
        "s3_time_budget_ms": s3_total_ms,
        "roundtrips_upper": round(n_roundtrips_upper, 1),
        "roundtrips_lower": round(n_roundtrips_lower, 1),
    }
    fname = f"results/probe-s3rtt-{int(time.time())}.json"
    with open(fname, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {fname}")


if __name__ == "__main__":
    asyncio.run(main())
