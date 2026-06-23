#!/usr/bin/env python3
"""
Reproduce turbopuffer vs Qdrant Cloud comparison experiments.
Saves results after each phase and skips completed phases on re-run.

Phases (in order):
  delete                — wipe comparison namespaces/collections from both DBs
  upload_dbpedia        — DBpedia 100K×1536 → tpuf serverless + Qdrant (batch=128)
  upload_dbpedia_pinned — DBpedia 100K×1536 → tpuf pinned-1r (single-replica write throughput)
  upload_hm             — H&M 105K×2048    → tpuf + Qdrant (batch=128)
  upload_multitenant    — random-768 1M×100 tenants → tpuf (100 ns) + Qdrant (payload_m=16)
  search_dbpedia_warm   — DBpedia warm: p=1, p=8 — tpuf serverless + Qdrant
  search_dbpedia_fixedqps — DBpedia fixed QPS 1→50 ($ break-even data)
  search_hm_warm        — H&M warm: tpuf pinned-4r p=32 + Qdrant p=1,8,32
  search_hm_cold        — H&M cold: tpuf pinned-4r cold + Qdrant p=32 (always warm)
  search_multitenant    — ns-per-tenant (tpuf) vs payload_m=16 (Qdrant)

Usage:
  cd ~/vector-db-benchmark
  set -a && source .env && set +a
  python scripts/reproduce_comparison.py
  python scripts/reproduce_comparison.py --resume results/reproduce-2026-.../
  python scripts/reproduce_comparison.py --only search_dbpedia_warm search_dbpedia_fixedqps
  python scripts/reproduce_comparison.py --skip upload_multitenant --skip-pinned
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
import numpy as np

try:
    import turbopuffer as tpuf
    from qdrant_client import AsyncQdrantClient, models
except ImportError:
    print("ERROR: activate the poetry venv first")
    sys.exit(1)

# ── Dataset paths ──────────────────────────────────────────────────────────────
BASE     = Path(__file__).parent.parent
DBPEDIA  = BASE / "datasets/dbpedia-openai-100K-1536-angular/dbpedia_openai_100K"
HM       = BASE / "datasets/h-and-m-2048-angular/hnm"
MT       = BASE / "datasets/random-768-100-tenants/random_keywords_1m_768_vocab_100"

# ── Namespace / collection names ───────────────────────────────────────────────
TPUF_DBPEDIA        = "reproduce-dbpedia-100k-1536"
TPUF_DBPEDIA_PINNED = "reproduce-dbpedia-pinned-1r"
TPUF_HM             = "reproduce-hm-105k-2048"
TPUF_MT_PFX         = "reproduce-mt-"      # + tenant value

QDRANT_DBPEDIA = "reproduce-dbpedia"
QDRANT_HM      = "reproduce-hm"
QDRANT_MT      = "reproduce-multitenant"

# ── Benchmark params ───────────────────────────────────────────────────────────
BATCH_SIZE        = 128
N_SEARCH          = 1000
N_WARM_HM         = 80
FIXED_QPS_LEVELS  = [1, 5, 10, 20, 50]
FIXED_QPS_SECS    = 120
PINNED_REPLICAS   = 4

PHASES = [
    "delete",
    "upload_dbpedia",
    "upload_dbpedia_pinned",
    "upload_hm",
    "upload_multitenant",
    "search_dbpedia_warm",
    "search_dbpedia_fixedqps",
    "search_hm_warm",
    "search_hm_cold",
    "search_multitenant",
    "concurrent_write_read",
]

# tpuf DBpedia 100K×1536 cost constants (from pricing analysis)
TPUF_COST_PER_QUERY  = 1.28 / 1_000_000   # $0.001/TB × 1.28GB min
TPUF_STORAGE_MONTHLY = 0.10                 # $0.33/GB × 0.308 GB
QDRANT_DBPEDIA_MONTHLY = 26.10             # 1 node, 2 GiB, AWS us-west-2

SECS_PER_MONTH = 30 * 24 * 3600


# ── State ──────────────────────────────────────────────────────────────────────

def load_state(run_dir: Path) -> dict:
    p = run_dir / "state.json"
    return json.loads(p.read_text()) if p.exists() else {"phases": {}}

def save_state(run_dir: Path, state: dict):
    (run_dir / "state.json").write_text(json.dumps(state, indent=2))

def mark_done(run_dir: Path, state: dict, phase: str, results: dict):
    state["phases"][phase] = {
        "status": "done",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": results,
    }
    save_state(run_dir, state)
    print(f"  [saved → {run_dir}/state.json]")

def is_done(state: dict, phase: str) -> bool:
    return state.get("phases", {}).get(phase, {}).get("status") == "done"


# ── Stats ──────────────────────────────────────────────────────────────────────

def stats(lats_s: list) -> dict:
    if not lats_s:
        return {}
    a = np.array(lats_s) * 1000
    total = float(np.sum(np.array(lats_s)))
    return {
        "n":       len(lats_s),
        "rps":     round(len(lats_s) / total, 1) if total > 0 else 0,
        "mean_ms": round(float(a.mean()), 1),
        "p50_ms":  round(float(np.percentile(a, 50)), 1),
        "p95_ms":  round(float(np.percentile(a, 95)), 1),
        "p99_ms":  round(float(np.percentile(a, 99)), 1),
    }

def recall_at_k(returned_ids, truth_ids, k=10):
    return len(set(list(returned_ids)[:k]) & set(list(truth_ids)[:k])) / k

def pstats(label: str, s: dict, extra: str = ""):
    print(f"  {label:42s}  n={s.get('n',0):5d}  RPS={s.get('rps',0):6.1f}"
          f"  p50={s.get('p50_ms',0):6.1f}ms  p99={s.get('p99_ms',0):6.1f}ms  {extra}")


# ── Filter converters ──────────────────────────────────────────────────────────

def to_tpuf_filter(cond: dict):
    """Translate Qdrant-style conditions to tpuf tuple filter format."""
    if not cond:
        return None
    return _tpuf_clause(cond)

def _tpuf_clause(clause: dict):
    for field, val in clause.items():
        if field in ("and", "or", "must", "should"):
            op = "And" if field in ("and", "must") else "Or"
            return (op, [_tpuf_clause(c) for c in val])
        if field == "must_not":
            return ("Not", ("Or", [_tpuf_clause(c) for c in val]))
        match = val.get("match")
        if match is not None:
            if "value" in match:
                return (field, "Eq", match["value"])
            if "any" in match:
                return (field, "In", match["any"])
        rng = val.get("range")
        if rng is not None:
            parts = []
            for op_key, tpuf_op in [("gt","Gt"),("gte","Gte"),("lt","Lt"),("lte","Lte")]:
                if op_key in rng:
                    parts.append((field, tpuf_op, rng[op_key]))
            return ("And", parts) if len(parts) > 1 else parts[0]
    raise ValueError(f"Unknown filter clause: {clause}")

def to_qdrant_filter(cond: dict):
    if not cond:
        return None
    musts = [_qdrant_fc(c) for c in cond["and"]] if "and" in cond else [_qdrant_fc(cond)]
    return models.Filter(must=musts)

def _qdrant_fc(cond: dict):
    for field, op in cond.items():
        if "match" in op:
            return models.FieldCondition(key=field, match=models.MatchValue(value=op["match"]["value"]))
    raise ValueError(f"Unknown fc: {cond}")


# ── Engine clients ─────────────────────────────────────────────────────────────

def make_tpuf():
    return tpuf.AsyncTurbopuffer(
        api_key=os.environ["TURBOPUFFER_API_KEY"],
        region=os.environ.get("TURBOPUFFER_REGION", "aws-us-west-2"),
    )

def make_qdrant():
    return AsyncQdrantClient(
        url=os.environ["QDRANT_CLUSTER_URL"],
        api_key=os.environ.get("QDRANT_API_KEY"),
        check_compatibility=False,
        timeout=120,
    )


# ── Upload helpers ─────────────────────────────────────────────────────────────

def _upload_stats(total, batch_lats, t_total):
    batch_lats_arr = np.array(batch_lats)
    wps = round(total / t_total, 1)
    return {
        "total_s":    round(t_total, 1),
        "wps":        wps,
        "batch_p50_ms": round(float(np.percentile(batch_lats_arr, 50)) * 1000, 1),
        "batch_p99_ms": round(float(np.percentile(batch_lats_arr, 99)) * 1000, 1),
    }

async def tpuf_upload(ns, ids, vectors, extra_cols=None):
    total = len(ids)
    t0 = time.perf_counter()
    batch_lats = []
    server_ms_list = []
    billable_bytes = 0
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        cols = {"id": ids[start:end], "vector": vectors[start:end].tolist()}
        if extra_cols:
            for k, v in extra_cols.items():
                cols[k] = v[start:end]
        kwargs = {"upsert_columns": cols, "distance_metric": "cosine_distance"}
        bt = time.perf_counter()
        resp = await ns.write(**kwargs)
        batch_lats.append(time.perf_counter() - bt)
        if resp.performance:
            server_ms_list.append(resp.performance.server_total_ms)
        if resp.billing:
            billable_bytes += resp.billing.billable_logical_bytes_written
        if (start // BATCH_SIZE) % 20 == 0:
            print(f"    tpuf {end}/{total}", flush=True)
    s = _upload_stats(total, batch_lats, time.perf_counter() - t0)
    if server_ms_list:
        arr = np.array(server_ms_list)
        s["server_p50_ms"] = round(float(np.percentile(arr, 50)), 1)
        s["server_p99_ms"] = round(float(np.percentile(arr, 99)), 1)
    if billable_bytes:
        s["billable_gb"] = round(billable_bytes / 1e9, 4)
    return s

async def qdrant_stored_gb(collection_name):
    """Query /telemetry?details_level=10 and return vectors+payload bytes for a collection."""
    url = os.environ["QDRANT_CLUSTER_URL"].rstrip("/") + "/telemetry?details_level=10"
    api_key = os.environ.get("QDRANT_API_KEY")
    headers = {"api-key": api_key} if api_key else {}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
    data = resp.json()
    for col in data.get("result", {}).get("collections", {}).get("collections", []):
        if col["id"] != collection_name:
            continue
        total_bytes = 0
        for shard in col.get("shards", []):
            local = shard.get("local", {})
            total_bytes += local.get("vectors_size_bytes", 0)
            total_bytes += local.get("payloads_size_bytes", 0)
        return round(total_bytes / 1e9, 4) if total_bytes else None
    return None


async def qdrant_upsert_timed(collection, points_dicts):
    """POST to Qdrant REST API directly to capture server-side processing time.
    Returns server_time_ms from the response 'time' field (seconds → ms)."""
    url = os.environ["QDRANT_CLUSTER_URL"].rstrip("/") + f"/collections/{collection}/points"
    api_key = os.environ.get("QDRANT_API_KEY")
    headers = {"api-key": api_key, "Content-Type": "application/json"} if api_key else {"Content-Type": "application/json"}
    body = {"points": points_dicts}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.put(url, json=body, headers=headers)
        resp.raise_for_status()
    return resp.json().get("time", 0) * 1000  # seconds → ms


async def qdrant_upload(qc, collection, vectors, ids, payloads=None):
    total = len(ids)
    t0 = time.perf_counter()
    batch_lats = []
    server_ms_list = []
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        points_dicts = [
            {
                "id": int(ids[start + i]),
                "vector": vec.tolist(),
                **({"payload": payloads[start + i]} if payloads else {}),
            }
            for i, vec in enumerate(vectors[start:end])
        ]
        bt = time.perf_counter()
        server_ms = await qdrant_upsert_timed(collection, points_dicts)
        batch_lats.append(time.perf_counter() - bt)
        server_ms_list.append(server_ms)
        if (start // BATCH_SIZE) % 20 == 0:
            print(f"    qdrant {end}/{total}", flush=True)
    t_upsert = time.perf_counter() - t0
    print("  Waiting for Qdrant indexing...", flush=True)
    while True:
        info = await qc.get_collection(collection)
        if info.status == models.CollectionStatus.GREEN:
            break
        print(f"    status={info.status}", flush=True)
        await asyncio.sleep(5)
    t_total = time.perf_counter() - t0
    s = _upload_stats(total, batch_lats, t_upsert)
    s["index_s"]  = round(t_total - t_upsert, 1)
    s["total_s"]  = round(t_total, 1)
    if server_ms_list:
        arr = np.array(server_ms_list)
        s["server_p50_ms"] = round(float(np.percentile(arr, 50)), 1)
        s["server_p99_ms"] = round(float(np.percentile(arr, 99)), 1)
    stored_gb = await qdrant_stored_gb(collection)
    if stored_gb is not None:
        s["stored_gb"] = stored_gb
    return s

def report_upload(label, r):
    tpuf = r["tpuf"]
    qt   = r["qdrant"]
    print(f"\n  ┌─ Upload: {label}  batch={r['batch']}")
    print(f"  │  turbopuffer  total={tpuf['total_s']/60:.1f}min  wps={tpuf['wps']}  batch p50={tpuf['batch_p50_ms']}ms  p99={tpuf['batch_p99_ms']}ms")
    print(f"  │  Qdrant       total={qt['total_s']/60:.1f}min  wps={qt['wps']}  batch p50={qt['batch_p50_ms']}ms  p99={qt['batch_p99_ms']}ms")
    print(f"  └─    Qdrant upsert={qt['total_s']/60 - qt['index_s']/60:.1f}min  index={qt['index_s']/60:.1f}min")


# ── Pinning helpers ────────────────────────────────────────────────────────────

async def pin_and_wait(ns, replicas=PINNED_REPLICAS, timeout=360):
    print(f"  Pinning {ns.id} → {replicas}r ...", flush=True)
    await ns.update_metadata(pinning={"replicas": replicas})
    deadline = time.time() + timeout
    while time.time() < deadline:
        meta  = await ns.metadata()
        pin   = getattr(meta, "pinning", None)
        st    = getattr(pin, "status", None) if pin else None
        ready = getattr(st, "ready_replicas", 0) if st else 0
        print(f"    ready_replicas={ready}/{replicas}", flush=True)
        if ready >= replicas:
            print("  Pinned ✓")
            return True
        await asyncio.sleep(10)
    print("  WARNING: pin timeout")
    return False

async def unpin(ns):
    try:
        await ns.update_metadata(pinning=None)
        print(f"  Unpinned {ns.id}")
    except Exception as e:
        print(f"  Unpin error: {e}")


# ── Benchmark primitives ───────────────────────────────────────────────────────

def _tpuf_perf(r):
    """Extract perf+billing dict from a tpuf NamespaceQueryResponse."""
    return {
        "server_total_ms":        r.performance.server_total_ms,
        "query_execution_ms":     r.performance.query_execution_ms,
        "cache_hit_ratio":        r.performance.cache_hit_ratio,
        "cache_temperature":      r.performance.cache_temperature,
        "exhaustive_search_count": r.performance.exhaustive_search_count,
        "billable_bytes":         r.billing.billable_logical_bytes_queried,
    }

async def run_search(query_fn, tests, concurrency, n=N_SEARCH, collect_perf=False):
    """Fire n queries at given concurrency.

    query_fn(vec, cond) should return either:
      - list[id]                    (plain mode)
      - (list[id], perf_dict|None)  (when collect_perf=True, tpuf paths)
      - (list[id], qdrant_server_ms|None)  (qdrant paths always return server_ms)
    """
    sem = asyncio.Semaphore(concurrency)
    latencies = []
    returned  = [None] * n  # pre-allocated so index == dispatch order
    tpuf_perf_rows  = []
    qdrant_server_ms = []

    async def one(i, t):
        async with sem:
            t0 = time.perf_counter()
            result = await query_fn(t["query"], t.get("conditions") or {})
            latencies.append(time.perf_counter() - t0)
            if isinstance(result, tuple):
                ids, meta = result
                returned[i] = ids
                if collect_perf and meta and isinstance(meta, dict):
                    tpuf_perf_rows.append(meta)
                elif meta is not None and isinstance(meta, (int, float)):
                    qdrant_server_ms.append(meta)
            else:
                returned[i] = result

    await asyncio.gather(*[one(i, tests[i % len(tests)]) for i in range(n)])

    s = stats(latencies)
    recalls = [recall_at_k(returned[i], tests[i % len(tests)]["closest_ids"]) for i in range(n)]
    s["recall_pct"] = round(float(np.mean(recalls)) * 100, 2)

    if tpuf_perf_rows:
        srv    = np.array([p["server_total_ms"]        for p in tpuf_perf_rows])
        exe    = np.array([p["query_execution_ms"]     for p in tpuf_perf_rows])
        hit    = np.array([p["cache_hit_ratio"]        for p in tpuf_perf_rows])
        billed = np.array([p["billable_bytes"]         for p in tpuf_perf_rows])
        exh    = np.array([p["exhaustive_search_count"] for p in tpuf_perf_rows])
        s["tpuf_server_p50_ms"]   = round(float(np.percentile(srv, 50)), 1)
        s["tpuf_server_p99_ms"]   = round(float(np.percentile(srv, 99)), 1)
        s["tpuf_exec_p50_ms"]     = round(float(np.percentile(exe, 50)), 1)
        s["tpuf_exec_p99_ms"]     = round(float(np.percentile(exe, 99)), 1)
        s["tpuf_cache_hit_avg"]   = round(float(np.mean(hit)), 3)
        s["tpuf_billed_gb_avg"]   = round(float(np.mean(billed)) / 1e9, 6)
        s["tpuf_exhaustive_avg"]  = round(float(np.mean(exh)), 1)
        temps = [p["cache_temperature"] for p in tpuf_perf_rows]
        s["tpuf_cache_temp"]      = max(set(temps), key=temps.count)  # mode

    if qdrant_server_ms:
        arr = np.array(qdrant_server_ms)
        s["qdrant_server_p50_ms"] = round(float(np.percentile(arr, 50)), 3)
        s["qdrant_server_p99_ms"] = round(float(np.percentile(arr, 99)), 3)

    return s

async def fixed_qps_run(query_fn, qps: float, duration_s: int, server_ms_sink=None) -> list:
    """Dispatch queries at target QPS for duration_s seconds.

    query_fn() may return a server_ms float; if server_ms_sink list is provided it is appended.
    """
    interval = 1.0 / qps
    deadline = time.monotonic() + duration_s
    latencies = []
    in_flight = set()

    async def one():
        t0 = time.perf_counter()
        try:
            result = await query_fn()
            if server_ms_sink is not None and isinstance(result, (int, float)):
                server_ms_sink.append(result)
        except Exception:
            pass
        latencies.append(time.perf_counter() - t0)

    next_fire = time.monotonic()

    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_fire:
            t = asyncio.create_task(one())
            in_flight.add(t)
            t.add_done_callback(in_flight.discard)
            next_fire += interval
        sleep = next_fire - time.monotonic()
        await asyncio.sleep(min(max(sleep, 0), 0.05))

    if in_flight:
        await asyncio.gather(*in_flight, return_exceptions=True)
    return latencies


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 0: delete
# ═══════════════════════════════════════════════════════════════════════════════

async def phase_delete(run_dir, state, args):
    print("\n═══ delete ═══")
    tc = make_tpuf()
    qc = make_qdrant()

    to_del_tpuf = [TPUF_DBPEDIA, TPUF_DBPEDIA_PINNED, TPUF_HM]
    try:
        async for ns in tc.namespaces():
            if ns.id.startswith(TPUF_MT_PFX):
                to_del_tpuf.append(ns.id)
    except Exception:
        pass

    for name in to_del_tpuf:
        try:
            await tc.namespace(name).delete_all()
            print(f"  tpuf ✓ {name}")
        except Exception as e:
            print(f"  tpuf skip {name}: {e}")

    for name in [QDRANT_DBPEDIA, QDRANT_HM, QDRANT_MT]:
        try:
            await qc.delete_collection(name)
            print(f"  qdrant ✓ {name}")
        except Exception as e:
            print(f"  qdrant skip {name}: {e}")

    await qc.close()
    mark_done(run_dir, state, "delete", {})


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: upload_dbpedia
# ═══════════════════════════════════════════════════════════════════════════════

async def phase_upload_dbpedia(run_dir, state, args):
    print("\n═══ upload_dbpedia ═══")
    vecs = np.load(DBPEDIA / "vectors.npy")
    ids  = list(range(len(vecs)))
    print(f"  {vecs.shape[0]} × {vecs.shape[1]}, batch={BATCH_SIZE}")

    tc = make_tpuf()
    tpuf = await tpuf_upload(tc.namespace(TPUF_DBPEDIA), ids, vecs)
    print(f"  tpuf: {tpuf['total_s']/60:.1f} min  wps={tpuf['wps']}")

    qc = make_qdrant()
    await qc.create_collection(
        collection_name=QDRANT_DBPEDIA,
        vectors_config=models.VectorParams(size=vecs.shape[1], distance=models.Distance.COSINE),
        hnsw_config=models.HnswConfigDiff(m=16, ef_construct=128),
        optimizers_config=models.OptimizersConfigDiff(memmap_threshold=10_000_000),
    )
    qt = await qdrant_upload(qc, QDRANT_DBPEDIA, vecs, ids)
    print(f"  qdrant: upsert {(qt['total_s']-qt['index_s'])/60:.1f} min  index {qt['index_s']/60:.1f} min  total {qt['total_s']/60:.1f} min  wps={qt['wps']}")
    await qc.close()

    r = {"tpuf": tpuf, "qdrant": qt, "batch": BATCH_SIZE}
    mark_done(run_dir, state, "upload_dbpedia", r)
    report_upload("DBpedia 100K×1536", r)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1b: upload_dbpedia_pinned
# Upload DBpedia into a pinned-1r namespace to measure single-replica write
# throughput and compare server-side write latency vs serverless.
# ═══════════════════════════════════════════════════════════════════════════════

async def phase_upload_dbpedia_pinned(run_dir, state, args):
    if args.skip_pinned:
        print("\n═══ upload_dbpedia_pinned (skipped — --skip-pinned) ═══")
        return
    print("\n═══ upload_dbpedia_pinned ═══")
    vecs = np.load(DBPEDIA / "vectors.npy")
    ids  = list(range(len(vecs)))
    print(f"  {vecs.shape[0]} × {vecs.shape[1]}, batch={BATCH_SIZE}, pinned-1r")

    tc = make_tpuf()
    ns = tc.namespace(TPUF_DBPEDIA_PINNED)

    # Write one seed batch so the namespace exists before pinning.
    seed_cols = {"id": ids[:BATCH_SIZE], "vector": vecs[:BATCH_SIZE].tolist()}
    await ns.write(upsert_columns=seed_cols, distance_metric="cosine_distance")
    print("  Seed batch written — pinning namespace...")

    await pin_and_wait(ns, replicas=1)

    # Upload all vectors (including the seed batch — idempotent upsert).
    tpuf = await tpuf_upload(ns, ids, vecs)
    print(f"  tpuf pinned-1r: {tpuf['total_s']/60:.1f} min  wps={tpuf['wps']}")

    await unpin(ns)

    r = {"tpuf_pinned_1r": tpuf, "batch": BATCH_SIZE}
    mark_done(run_dir, state, "upload_dbpedia_pinned", r)
    sv = tpuf.get("server_p50_ms", "?")
    sv99 = tpuf.get("server_p99_ms", "?")
    bg = tpuf.get("billable_gb", "?")
    print(f"\n  ┌─ Upload: DBpedia 100K×1536 pinned-1r  batch={BATCH_SIZE}")
    print(f"  │  tpuf pinned-1r: {tpuf['total_s']/60:.1f} min  wps={tpuf['wps']}"
          f"  batch_p50={tpuf['batch_p50_ms']}ms  batch_p99={tpuf['batch_p99_ms']}ms"
          f"  server_p50={sv}ms  server_p99={sv99}ms  billable_gb={bg}")
    print(f"  └─")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: upload_hm
# ═══════════════════════════════════════════════════════════════════════════════

async def phase_upload_hm(run_dir, state, args):
    print("\n═══ upload_hm ═══")
    vecs     = np.load(HM / "vectors.npy")
    payloads = [json.loads(l) for l in open(HM / "payloads.jsonl")]
    fmeta    = json.loads((HM / "filters.json").read_text())
    fields   = [f["name"] for f in fmeta]
    ids      = list(range(len(vecs)))
    print(f"  {vecs.shape[0]} × {vecs.shape[1]}, {len(fields)} filter fields, batch={BATCH_SIZE}")

    tc = make_tpuf()
    extra = {f: [p.get(f) for p in payloads] for f in fields}
    tpuf = await tpuf_upload(tc.namespace(TPUF_HM), ids, vecs, extra_cols=extra)
    print(f"  tpuf: {tpuf['total_s']/60:.1f} min  wps={tpuf['wps']}")

    qc = make_qdrant()
    await qc.create_collection(
        collection_name=QDRANT_HM,
        vectors_config=models.VectorParams(size=vecs.shape[1], distance=models.Distance.COSINE),
        hnsw_config=models.HnswConfigDiff(m=16, ef_construct=128),
        optimizers_config=models.OptimizersConfigDiff(memmap_threshold=10_000_000),
    )
    for field in fields:
        await qc.create_payload_index(
            collection_name=QDRANT_HM,
            field_name=field,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    qt = await qdrant_upload(qc, QDRANT_HM, vecs, ids, payloads=payloads)
    print(f"  qdrant: upsert {(qt['total_s']-qt['index_s'])/60:.1f} min  index {qt['index_s']/60:.1f} min  total {qt['total_s']/60:.1f} min  wps={qt['wps']}")
    await qc.close()

    r = {"tpuf": tpuf, "qdrant": qt, "batch": BATCH_SIZE}
    mark_done(run_dir, state, "upload_hm", r)
    report_upload("H&M 105K×2048", r)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: upload_multitenant
# ═══════════════════════════════════════════════════════════════════════════════

async def phase_upload_multitenant(run_dir, state, args):
    print("\n═══ upload_multitenant ═══")
    vecs     = np.load(MT / "vectors.npy")
    payloads = [json.loads(l) for l in open(MT / "payloads.jsonl")]
    ids      = list(range(len(vecs)))
    tenants  = sorted(set(p["a"] for p in payloads))
    groups   = {t: [i for i, p in enumerate(payloads) if p["a"] == t] for t in tenants}
    print(f"  {vecs.shape[0]} × {vecs.shape[1]}, {len(tenants)} tenants × {len(groups[tenants[0]])} vecs")

    # tpuf: 100 namespaces in parallel (max 10 concurrent)
    # wall-clock is the right measure here (parallel writes); wps = total vectors / wall time
    tc = make_tpuf()
    sem = asyncio.Semaphore(10)
    t0 = time.perf_counter()
    all_batch_lats = []
    all_billable_gb = []

    async def upload_tenant(tenant_val):
        async with sem:
            idxs = groups[tenant_val]
            s = await tpuf_upload(
                tc.namespace(f"{TPUF_MT_PFX}{tenant_val}"),
                [ids[i] for i in idxs],
                vecs[idxs],
            )
            all_batch_lats.extend([s["batch_p50_ms"], s["batch_p99_ms"]])  # approximate aggregate
            if "billable_gb" in s:
                all_billable_gb.append(s["billable_gb"])

    await asyncio.gather(*[upload_tenant(t) for t in tenants])
    wall_s = time.perf_counter() - t0
    tpuf = {
        "total_s": round(wall_s, 1),
        "wps": round(len(ids) / wall_s, 1),
        "batch_p50_ms": round(float(np.percentile(all_batch_lats, 50)), 1),
        "batch_p99_ms": round(float(np.percentile(all_batch_lats, 99)), 1),
    }
    if all_billable_gb:
        tpuf["billable_gb"] = round(sum(all_billable_gb), 4)  # total across all namespaces
    print(f"  tpuf: {tpuf['total_s']/60:.1f} min ({len(tenants)} namespaces)  wps={tpuf['wps']}")

    # Qdrant: single collection, m=0, payload_m=16, is_tenant on field "a"
    qc = make_qdrant()
    # Delete if exists from a partial prior run (phase not yet marked done)
    try:
        await qc.delete_collection(QDRANT_MT)
    except Exception:
        pass
    await qc.create_collection(
        collection_name=QDRANT_MT,
        vectors_config=models.VectorParams(size=vecs.shape[1], distance=models.Distance.COSINE),
        hnsw_config=models.HnswConfigDiff(m=0, payload_m=16),
        optimizers_config=models.OptimizersConfigDiff(memmap_threshold=10_000_000),
    )
    await qc.create_payload_index(
        collection_name=QDRANT_MT,
        field_name="a",
        field_schema=models.KeywordIndexParams(type="keyword", is_tenant=True),
    )
    qt = await qdrant_upload(qc, QDRANT_MT, vecs, ids, payloads=payloads)
    print(f"  qdrant: upsert {(qt['total_s']-qt['index_s'])/60:.1f} min  index {qt['index_s']/60:.1f} min  total {qt['total_s']/60:.1f} min  wps={qt['wps']}")
    await qc.close()

    r = {"tpuf": tpuf, "qdrant": qt, "batch": BATCH_SIZE, "tenants": len(tenants)}
    mark_done(run_dir, state, "upload_multitenant", r)
    report_upload(f"multi-tenant ({len(tenants)} ns vs 1 collection)", r)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: search_dbpedia_warm
# ═══════════════════════════════════════════════════════════════════════════════

async def phase_search_dbpedia_warm(run_dir, state, args):
    print("\n═══ search_dbpedia_warm ═══")
    tests = [json.loads(l) for l in open(DBPEDIA / "tests.jsonl")]
    tc = make_tpuf()
    qc = make_qdrant()
    ns = tc.namespace(TPUF_DBPEDIA)
    results = {}

    for p in [1, 8]:
        async def tpuf_q(vec, cond, _ns=ns):
            r = await _ns.query(rank_by=("vector", "ANN", vec), top_k=10, include_attributes=False)
            return ([x.id for x in r.rows], _tpuf_perf(r))

        s = await run_search(tpuf_q, tests, concurrency=p, collect_perf=True)
        results[f"tpuf_p{p}"] = s
        pstats(f"tpuf serverless p={p}", s, f"recall={s['recall_pct']}%  cache={s.get('tpuf_cache_temp','?')}  hit={s.get('tpuf_cache_hit_avg','?')}")

        async def qdrant_q(vec, cond, _qc=qc):
            raw = await _qc.http.search_api.query_points(
                collection_name=QDRANT_DBPEDIA,
                query_request=models.QueryRequest(
                    query=vec, params=models.SearchParams(hnsw_ef=128),
                    limit=10, with_vector=False, with_payload=False,
                ),
            )
            return ([pt.id for pt in raw.result.points], raw.time * 1000)

        s = await run_search(qdrant_q, tests, concurrency=p)
        results[f"qdrant_p{p}"] = s
        pstats(f"qdrant p={p}", s, f"recall={s['recall_pct']}%")

    await qc.close()
    mark_done(run_dir, state, "search_dbpedia_warm", results)
    _report_search("DBpedia warm", results)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5: search_dbpedia_fixedqps
# ═══════════════════════════════════════════════════════════════════════════════

async def phase_search_dbpedia_fixedqps(run_dir, state, args):
    print("\n═══ search_dbpedia_fixedqps ($ break-even) ═══")
    tests  = [json.loads(l) for l in open(DBPEDIA / "tests.jsonl")]
    vecs   = [t["query"] for t in tests]
    tc = make_tpuf()
    qc = make_qdrant()
    ns = tc.namespace(TPUF_DBPEDIA)
    results = {}

    for qps in FIXED_QPS_LEVELS:
        print(f"\n  ── QPS={qps} ({FIXED_QPS_SECS}s each) ──")

        idx_t = [0]
        tpuf_srv_ms = []
        async def tpuf_qfn(_ns=ns, _vecs=vecs, _idx=idx_t):
            vec = _vecs[_idx[0] % len(_vecs)]
            _idx[0] += 1
            r = await _ns.query(rank_by=("vector", "ANN", vec), top_k=10, include_attributes=False)
            return r.performance.server_total_ms

        lats = await fixed_qps_run(tpuf_qfn, qps, FIXED_QPS_SECS, server_ms_sink=tpuf_srv_ms)
        s = stats(lats)
        monthly_cost = TPUF_STORAGE_MONTHLY + qps * SECS_PER_MONTH * TPUF_COST_PER_QUERY
        s["monthly_usd"] = round(monthly_cost, 2)
        if tpuf_srv_ms:
            arr = np.array(tpuf_srv_ms)
            s["tpuf_server_p50_ms"] = round(float(np.percentile(arr, 50)), 1)
            s["tpuf_server_p99_ms"] = round(float(np.percentile(arr, 99)), 1)
        results[f"tpuf_qps{qps}"] = s
        pstats(f"  tpuf @ {qps} QPS", s, f"→ ${monthly_cost:.2f}/mo")

        idx_q = [0]
        qdrant_srv_ms = []
        async def qdrant_qfn(_qc=qc, _vecs=vecs, _idx=idx_q):
            vec = _vecs[_idx[0] % len(_vecs)]
            _idx[0] += 1
            raw = await _qc.http.search_api.query_points(
                collection_name=QDRANT_DBPEDIA,
                query_request=models.QueryRequest(
                    query=vec, params=models.SearchParams(hnsw_ef=128),
                    limit=10, with_vector=False, with_payload=False,
                ),
            )
            return raw.time * 1000

        lats = await fixed_qps_run(qdrant_qfn, qps, FIXED_QPS_SECS, server_ms_sink=qdrant_srv_ms)
        s = stats(lats)
        s["monthly_usd"] = QDRANT_DBPEDIA_MONTHLY
        if qdrant_srv_ms:
            arr = np.array(qdrant_srv_ms)
            s["qdrant_server_p50_ms"] = round(float(np.percentile(arr, 50)), 3)
            s["qdrant_server_p99_ms"] = round(float(np.percentile(arr, 99)), 3)
        results[f"qdrant_qps{qps}"] = s
        pstats(f"  qdrant @ {qps} QPS", s, f"→ ${QDRANT_DBPEDIA_MONTHLY:.2f}/mo (fixed)")

    await qc.close()
    mark_done(run_dir, state, "search_dbpedia_fixedqps", results)
    _report_fixedqps(results)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6: search_hm_warm
# ═══════════════════════════════════════════════════════════════════════════════

async def phase_search_hm_warm(run_dir, state, args):
    print("\n═══ search_hm_warm ═══")
    tests = [json.loads(l) for l in open(HM / "tests.jsonl")]
    tc = make_tpuf()
    qc = make_qdrant()
    ns = tc.namespace(TPUF_HM)
    results = {}

    if not args.skip_pinned:
        try:
            await pin_and_wait(ns)
            print(f"  Warming ({N_WARM_HM} queries)...")
            for i in range(N_WARM_HM):
                t = tests[i % len(tests)]
                await ns.query(
                    rank_by=("vector", "ANN", t["query"]),
                    top_k=10,
                    filters=to_tpuf_filter(t.get("conditions") or {}),
                    include_attributes=False,
                )

            async def tpuf_q(vec, cond, _ns=ns):
                r = await _ns.query(
                    rank_by=("vector", "ANN", vec), top_k=10,
                    filters=to_tpuf_filter(cond),
                    include_attributes=False,
                )
                perf = {"server_total_ms": r.performance.server_total_ms,
                        "query_execution_ms": r.performance.query_execution_ms,
                        "cache_hit_ratio": r.performance.cache_hit_ratio,
                        "cache_temperature": r.performance.cache_temperature,
                        "billable_bytes": r.billing.billable_logical_bytes_queried}
                return ([x.id for x in r.rows], perf)

            s = await run_search(tpuf_q, tests, concurrency=32, collect_perf=True)
            results["tpuf_pinned4r_p32_warm"] = s
            pstats("tpuf pinned-4r p=32 warm", s, f"recall={s['recall_pct']}%  cache={s.get('tpuf_cache_temp','?')}  hit={s.get('tpuf_cache_hit_avg','?')}")
        finally:
            await unpin(ns)
    else:
        print("  Skipping tpuf pinned (--skip-pinned)")

    # Qdrant: always warm
    for p in [1, 8, 32]:
        async def qdrant_q(vec, cond, _qc=qc):
            raw = await _qc.http.search_api.query_points(
                collection_name=QDRANT_HM,
                query_request=models.QueryRequest(
                    query=vec,
                    filter=to_qdrant_filter(cond),
                    params=models.SearchParams(hnsw_ef=128),
                    limit=10, with_vector=False, with_payload=False,
                ),
            )
            return ([pt.id for pt in raw.result.points], raw.time * 1000)

        s = await run_search(qdrant_q, tests, concurrency=p)
        results[f"qdrant_p{p}_warm"] = s
        pstats(f"qdrant p={p} warm", s, f"recall={s['recall_pct']}%")

    await qc.close()
    mark_done(run_dir, state, "search_hm_warm", results)
    _report_search("H&M warm", results)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7: search_hm_cold
# ═══════════════════════════════════════════════════════════════════════════════

async def phase_search_hm_cold(run_dir, state, args):
    print("\n═══ search_hm_cold ═══")
    tests = [json.loads(l) for l in open(HM / "tests.jsonl")]
    tc = make_tpuf()
    qc = make_qdrant()
    cold_name = f"{TPUF_HM}-cold"
    results = {}

    if not args.skip_pinned:
        cold_ns = tc.namespace(cold_name)
        try:
            # Delete any leftover from a prior interrupted run
            try:
                await cold_ns.delete_all()
                print(f"  Cleared stale {cold_name}")
            except Exception:
                pass
            print(f"  Copying {TPUF_HM} → {cold_name} (guaranteed cold)...")
            await cold_ns.copy_from(source_namespace=TPUF_HM)
            await asyncio.sleep(3)
            await pin_and_wait(cold_ns)

            # No warmup — run cold immediately
            async def tpuf_q_cold(vec, cond, _ns=cold_ns):
                r = await _ns.query(
                    rank_by=("vector", "ANN", vec), top_k=10,
                    filters=to_tpuf_filter(cond),
                    include_attributes=False,
                )
                perf = {"server_total_ms": r.performance.server_total_ms,
                        "query_execution_ms": r.performance.query_execution_ms,
                        "cache_hit_ratio": r.performance.cache_hit_ratio,
                        "cache_temperature": r.performance.cache_temperature,
                        "billable_bytes": r.billing.billable_logical_bytes_queried}
                return ([x.id for x in r.rows], perf)

            s = await run_search(tpuf_q_cold, tests, concurrency=32, n=500, collect_perf=True)
            results["tpuf_pinned4r_p32_cold"] = s
            pstats("tpuf pinned-4r p=32 cold", s, f"recall={s['recall_pct']}%  cache={s.get('tpuf_cache_temp','?')}")
        finally:
            await unpin(cold_ns)
            try:
                await cold_ns.delete_all()
                print(f"  Cleaned up {cold_name}")
            except Exception:
                pass
    else:
        print("  Skipping tpuf cold (--skip-pinned)")

    # Qdrant: no cold start — run same benchmark for reference
    async def qdrant_q(vec, cond, _qc=qc):
        raw = await _qc.http.search_api.query_points(
            collection_name=QDRANT_HM,
            query_request=models.QueryRequest(
                query=vec,
                filter=to_qdrant_filter(cond),
                params=models.SearchParams(hnsw_ef=128),
                limit=10, with_vector=False, with_payload=False,
            ),
        )
        return [pt.id for pt in raw.result.points]

    s = await run_search(qdrant_q, tests, concurrency=32)
    results["qdrant_p32_always_warm"] = s
    pstats("qdrant p=32 (no cold-start)", s, f"recall={s['recall_pct']}%")

    await qc.close()
    mark_done(run_dir, state, "search_hm_cold", results)
    _report_search("H&M cold", results)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 8: search_multitenant
# ═══════════════════════════════════════════════════════════════════════════════

async def phase_search_multitenant(run_dir, state, args):
    print("\n═══ search_multitenant ═══")
    tests = [json.loads(l) for l in open(MT / "tests.jsonl")]
    tc = make_tpuf()
    qc = make_qdrant()
    ns_cache = {}
    results = {}

    # tpuf: route each query to the per-tenant namespace
    async def tpuf_q(vec, cond, _tc=tc):
        tenant_val = cond["and"][0]["a"]["match"]["value"]
        if tenant_val not in ns_cache:
            ns_cache[tenant_val] = _tc.namespace(f"{TPUF_MT_PFX}{tenant_val}")
        r = await ns_cache[tenant_val].query(
            rank_by=("vector", "ANN", vec), top_k=10, include_attributes=False,
        )
        perf = {"server_total_ms": r.performance.server_total_ms,
                "query_execution_ms": r.performance.query_execution_ms,
                "cache_hit_ratio": r.performance.cache_hit_ratio,
                "cache_temperature": r.performance.cache_temperature,
                "billable_bytes": r.billing.billable_logical_bytes_queried}
        return ([x.id for x in r.rows], perf)

    for p in [1, 8, 32]:
        s = await run_search(tpuf_q, tests, concurrency=p, collect_perf=True)
        results[f"tpuf_ns_per_tenant_p{p}"] = s
        pstats(f"tpuf ns-per-tenant p={p}", s, f"recall={s['recall_pct']}%  cache={s.get('tpuf_cache_temp','?')}")

    # Qdrant: single collection with payload_m=16, is_tenant filter
    async def qdrant_q(vec, cond, _qc=qc):
        raw = await _qc.http.search_api.query_points(
            collection_name=QDRANT_MT,
            query_request=models.QueryRequest(
                query=vec,
                filter=to_qdrant_filter(cond),
                params=models.SearchParams(hnsw_ef=128),
                limit=10, with_vector=False, with_payload=False,
            ),
        )
        return [pt.id for pt in raw.result.points]

    for p in [1, 8, 32]:
        s = await run_search(qdrant_q, tests, concurrency=p)
        results[f"qdrant_payload_m16_p{p}"] = s
        pstats(f"qdrant payload_m=16 p={p}", s, f"recall={s['recall_pct']}%")

    await qc.close()
    mark_done(run_dir, state, "search_multitenant", results)
    _report_search("Multi-tenant", results)


# ── Report helpers ─────────────────────────────────────────────────────────────

def _report_search(label, r):
    print(f"\n  ┌─ Search report: {label}")
    print(f"  │  {'Config':40s}  {'RPS':>7}  {'p50':>8}  {'p99':>8}  {'recall':>7}")
    for k, s in r.items():
        if isinstance(s, dict) and "rps" in s:
            print(f"  │  {k:40s}  {s['rps']:>7.1f}  {s['p50_ms']:>7.1f}ms  {s['p99_ms']:>7.1f}ms  {s.get('recall_pct','—'):>6}%")
    print(f"  └─")

def _report_fixedqps(r):
    print(f"\n  ┌─ Fixed QPS — DBpedia 100K×1536 ($ break-even)")
    print(f"  │  {'QPS':>5}  {'Queries/mo':>12}  {'tpuf $/mo':>10}  {'tpuf p99':>9}  {'Qdrant $/mo':>12}  {'Qdrant p99':>10}  Winner")
    for qps in FIXED_QPS_LEVELS:
        tk, qk = f"tpuf_qps{qps}", f"qdrant_qps{qps}"
        if tk not in r or qk not in r:
            continue
        ts, qs = r[tk], r[qk]
        qmo = qps * SECS_PER_MONTH
        winner = "tpuf" if ts["monthly_usd"] < qs["monthly_usd"] else "Qdrant"
        tp99 = f"{ts['p99_ms']:>8.1f}ms" if "p99_ms" in ts else "       N/A"
        qp99 = f"{qs['p99_ms']:>9.1f}ms" if "p99_ms" in qs else "        N/A"
        print(f"  │  {qps:>5}  {qmo:>12,.0f}  ${ts['monthly_usd']:>9.2f}  "
              f"{tp99}  ${qs['monthly_usd']:>11.2f}  {qp99}  {winner}")
    print(f"  └─")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE: concurrent_write_read
# ═══════════════════════════════════════════════════════════════════════════════

TPUF_DBPEDIA_RW   = "reproduce-dbpedia-100k-1536-rw"
QDRANT_DBPEDIA_RW = "reproduce-dbpedia-rw"
RW_POST_UPLOAD_S  = 120   # keep reading this many seconds after upload finishes
RW_READ_INTERVAL  = 0.5   # seconds between successive single queries

async def phase_concurrent_write_read(run_dir, state, args):
    print("\n═══ concurrent_write_read ═══")
    vecs  = np.load(DBPEDIA / "vectors.npy")
    ids   = list(range(len(vecs)))
    tests = [json.loads(l) for l in open(DBPEDIA / "tests.jsonl")]
    print(f"  {vecs.shape[0]} × {vecs.shape[1]}, {len(tests)} query vectors, batch={BATCH_SIZE}")

    t0 = time.perf_counter()   # experiment wall clock

    # ── shared event lists (appended from both tasks) ───────────────────────
    write_events  = []   # {wall_t, engine, vectors_written, batch_ms}
    read_events   = []   # {wall_t, engine, total_ms, ...engine-specific fields..., recall}
    qdrant_info_events = []  # {wall_t, vectors_count, indexed_vectors_count}
    upload_done   = {"tpuf": False, "qdrant": False}

    # ── tpuf setup ──────────────────────────────────────────────────────────
    tc = make_tpuf()
    tpuf_ns = tc.namespace(TPUF_DBPEDIA_RW)

    # ── Qdrant setup ────────────────────────────────────────────────────────
    qc = make_qdrant()
    await qc.create_collection(
        collection_name=QDRANT_DBPEDIA_RW,
        vectors_config=models.VectorParams(size=vecs.shape[1], distance=models.Distance.COSINE),
        hnsw_config=models.HnswConfigDiff(m=16, ef_construct=128),
        optimizers_config=models.OptimizersConfigDiff(memmap_threshold=10_000_000),
    )

    # ── Writer: tpuf ────────────────────────────────────────────────────────
    async def writer_tpuf():
        written = 0
        for start in range(0, len(ids), BATCH_SIZE):
            batch_ids  = ids[start:start + BATCH_SIZE]
            batch_vecs = vecs[start:start + BATCH_SIZE]
            t_batch = time.perf_counter()
            await tpuf_ns.upsert(
                ids=batch_ids,
                vectors=batch_vecs.tolist(),
            )
            ms = (time.perf_counter() - t_batch) * 1000
            written += len(batch_ids)
            write_events.append({
                "wall_t": round(time.perf_counter() - t0, 3),
                "engine": "tpuf",
                "vectors_written": written,
                "batch_ms": round(ms, 1),
            })
        upload_done["tpuf"] = True
        print(f"  tpuf writer done at t={time.perf_counter()-t0:.1f}s")

    # ── Writer: Qdrant ──────────────────────────────────────────────────────
    async def writer_qdrant():
        written = 0
        for start in range(0, len(ids), BATCH_SIZE):
            batch_ids  = ids[start:start + BATCH_SIZE]
            batch_vecs = vecs[start:start + BATCH_SIZE]
            points = [
                {"id": int(bid), "vector": batch_vecs[i].tolist()}
                for i, bid in enumerate(batch_ids)
            ]
            ms = await qdrant_upsert_timed(QDRANT_DBPEDIA_RW, points)
            written += len(batch_ids)
            write_events.append({
                "wall_t": round(time.perf_counter() - t0, 3),
                "engine": "qdrant",
                "vectors_written": written,
                "batch_ms": round(ms, 1),
            })
        upload_done["qdrant"] = True
        print(f"  qdrant writer done at t={time.perf_counter()-t0:.1f}s")

    # ── Reader: tpuf ────────────────────────────────────────────────────────
    async def reader_tpuf():
        await asyncio.sleep(1.0)   # let first batch land
        q_idx = 0
        while True:
            t_read = time.perf_counter()
            test   = tests[q_idx % len(tests)]
            q_idx += 1
            try:
                r = await tpuf_ns.query(
                    rank_by=("vector", "ANN", test["query"]),
                    top_k=10,
                    include_attributes=False,
                )
                elapsed_ms = (time.perf_counter() - t_read) * 1000
                p = r.performance
                b = r.billing
                returned_ids = [x.id for x in r.rows]
                rec = recall_at_k(returned_ids, test["closest_ids"])
                # staleness: seconds between last visible write and this query
                liwa = p.last_included_write_at
                staleness_ms = None
                if liwa is not None:
                    import datetime
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    staleness_ms = round((now_utc - liwa).total_seconds() * 1000, 1)
                read_events.append({
                    "wall_t":                round(time.perf_counter() - t0, 3),
                    "engine":                "tpuf",
                    "total_ms":              round(elapsed_ms, 1),
                    "server_total_ms":       p.server_total_ms,
                    "query_execution_ms":    p.query_execution_ms,
                    "cache_hit_ratio":       round(p.cache_hit_ratio, 3),
                    "cache_temperature":     p.cache_temperature,
                    "exhaustive_search_count": p.exhaustive_search_count,
                    "staleness_ms":          staleness_ms,
                    "billed_bytes":          b.billable_logical_bytes_queried if b else None,
                    "recall":                round(rec, 4),
                    "n_results":             len(returned_ids),
                })
            except Exception as e:
                read_events.append({
                    "wall_t": round(time.perf_counter() - t0, 3),
                    "engine": "tpuf",
                    "error":  str(e),
                })
            # stop RW_POST_UPLOAD_S after tpuf upload finishes
            if upload_done["tpuf"] and (time.perf_counter() - t0) > _upload_end_t.get("tpuf", 0) + RW_POST_UPLOAD_S:
                break
            await asyncio.sleep(RW_READ_INTERVAL)

    # ── Reader: Qdrant ──────────────────────────────────────────────────────
    async def reader_qdrant():
        await asyncio.sleep(1.0)
        q_idx = 0
        while True:
            t_read = time.perf_counter()
            test   = tests[q_idx % len(tests)]
            q_idx += 1
            try:
                raw = await qc.http.search_api.query_points(
                    collection_name=QDRANT_DBPEDIA_RW,
                    query_request=models.QueryRequest(
                        query=test["query"],
                        params=models.SearchParams(hnsw_ef=128),
                        limit=10, with_vector=False, with_payload=False,
                    ),
                )
                elapsed_ms = (time.perf_counter() - t_read) * 1000
                returned_ids = [pt.id for pt in raw.result.points]
                rec = recall_at_k(returned_ids, test["closest_ids"])
                read_events.append({
                    "wall_t":       round(time.perf_counter() - t0, 3),
                    "engine":       "qdrant",
                    "total_ms":     round(elapsed_ms, 1),
                    "server_ms":    round(raw.time * 1000, 1),
                    "recall":       round(rec, 4),
                    "n_results":    len(returned_ids),
                })
            except Exception as e:
                read_events.append({
                    "wall_t": round(time.perf_counter() - t0, 3),
                    "engine": "qdrant",
                    "error":  str(e),
                })
            if upload_done["qdrant"] and (time.perf_counter() - t0) > _upload_end_t["qdrant"] + RW_POST_UPLOAD_S:
                break
            await asyncio.sleep(RW_READ_INTERVAL)

    # ── Qdrant collection info poller ────────────────────────────────────────
    async def poller_qdrant():
        while not upload_done["qdrant"] or (time.perf_counter() - t0) < _upload_end_t.get("qdrant", 1e9) + RW_POST_UPLOAD_S:
            try:
                info = await qc.get_collection(QDRANT_DBPEDIA_RW)
                qdrant_info_events.append({
                    "wall_t":               round(time.perf_counter() - t0, 3),
                    "vectors_count":        info.vectors_count,
                    "indexed_vectors_count": info.indexed_vectors_count,
                })
            except Exception:
                pass
            await asyncio.sleep(5.0)
            if upload_done["qdrant"] and (time.perf_counter() - t0) > _upload_end_t.get("qdrant", 0) + RW_POST_UPLOAD_S:
                break

    # ── track upload end times ───────────────────────────────────────────────
    _upload_end_t = {}

    async def tracked_writer_tpuf():
        await writer_tpuf()
        _upload_end_t["tpuf"] = time.perf_counter() - t0

    async def tracked_writer_qdrant():
        await writer_qdrant()
        _upload_end_t["qdrant"] = time.perf_counter() - t0

    # ── run all tasks concurrently ───────────────────────────────────────────
    await asyncio.gather(
        tracked_writer_tpuf(),
        tracked_writer_qdrant(),
        reader_tpuf(),
        reader_qdrant(),
        poller_qdrant(),
    )

    await qc.close()

    result = {
        "write_events":       write_events,
        "read_events":        read_events,
        "qdrant_info_events": qdrant_info_events,
        "upload_end_t":       _upload_end_t,
        "n_queries":          len(tests),
        "n_vectors":          len(ids),
    }
    mark_done(run_dir, state, "concurrent_write_read", result)

    tpuf_reads  = [e for e in read_events  if e["engine"] == "tpuf"   and "error" not in e]
    qdrant_reads = [e for e in read_events if e["engine"] == "qdrant" and "error" not in e]
    print(f"\n  ┌─ Concurrent write+read summary")
    print(f"  │  tpuf upload done:   t={_upload_end_t.get('tpuf','?'):.1f}s")
    print(f"  │  qdrant upload done: t={_upload_end_t.get('qdrant','?'):.1f}s")
    print(f"  │  tpuf reads:   n={len(tpuf_reads)}"
          f"  p50={np.percentile([e['total_ms'] for e in tpuf_reads], 50):.1f}ms"
          f"  p99={np.percentile([e['total_ms'] for e in tpuf_reads], 99):.1f}ms"
          f"  recall_mean={np.mean([e['recall'] for e in tpuf_reads]):.3f}")
    print(f"  │  qdrant reads: n={len(qdrant_reads)}"
          f"  p50={np.percentile([e['total_ms'] for e in qdrant_reads], 50):.1f}ms"
          f"  p99={np.percentile([e['total_ms'] for e in qdrant_reads], 99):.1f}ms"
          f"  recall_mean={np.mean([e['recall'] for e in qdrant_reads]):.3f}")
    print(f"  └─")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

PHASE_FNS = {
    "delete":                   phase_delete,
    "upload_dbpedia":           phase_upload_dbpedia,
    "upload_dbpedia_pinned":    phase_upload_dbpedia_pinned,
    "upload_hm":                phase_upload_hm,
    "upload_multitenant":       phase_upload_multitenant,
    "search_dbpedia_warm":      phase_search_dbpedia_warm,
    "search_dbpedia_fixedqps":  phase_search_dbpedia_fixedqps,
    "search_hm_warm":           phase_search_hm_warm,
    "search_hm_cold":           phase_search_hm_cold,
    "search_multitenant":       phase_search_multitenant,
    "concurrent_write_read":    phase_concurrent_write_read,
}

async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resume", metavar="DIR", help="Resume from existing run directory")
    ap.add_argument("--only",   nargs="+", choices=PHASES, metavar="PHASE", help="Run only these phases")
    ap.add_argument("--skip",   nargs="+", choices=PHASES, metavar="PHASE", default=[], help="Skip these phases")
    ap.add_argument("--skip-pinned", action="store_true", help="Skip H&M pinned-replica phases")
    args = ap.parse_args()

    run_dir = Path(args.resume) if args.resume else Path(f"results/reproduce-{time.strftime('%Y-%m-%dT%H-%M-%S')}")
    run_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(run_dir)
    print(f"Run dir: {run_dir}")

    to_run = args.only if args.only else PHASES
    for phase in to_run:
        if phase in args.skip:
            print(f"\n  skip {phase} (--skip)")
            continue
        if is_done(state, phase):
            print(f"\n  skip {phase} (already done)")
            continue
        await PHASE_FNS[phase](run_dir, state, args)

    print(f"\n═══ All done → {run_dir}/state.json ═══")

if __name__ == "__main__":
    asyncio.run(main())
