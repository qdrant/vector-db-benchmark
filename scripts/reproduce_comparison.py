#!/usr/bin/env python3
"""
Reproduce turbopuffer vs Qdrant comparison experiments.

Experiment matrix: dataset × op × engine-variant
  Datasets:  dbpedia  (100K×1536, unfiltered ANN)
             hm       (105K×2048, filtered fashion)
             mt       (1M×768,    100-tenant isolation)
  Ops:       upload       — write all vectors, poll until indexed
             search       — warm search at p=1/8/32
             search_cold  — cold-start search (tpuf pinned); qdrant always-warm reference
             fixed_qps    — fixed-QPS sweep 1→50 for cost break-even
             write_read   — concurrent writes+reads within each engine
             disk         — Qdrant disk-backed collections (dbpedia only)
  Engines:   tpuf, tpuf_pinned_1r (upload), tpuf_pinned_4r (search),
             qdrant, qdrant_deferred

State keys: "dbpedia/upload/tpuf", "hm/search/qdrant", etc. — one per variant.

Usage:
  python scripts/reproduce_comparison.py
  python scripts/reproduce_comparison.py --dataset dbpedia
  python scripts/reproduce_comparison.py --dataset hm --op upload
  python scripts/reproduce_comparison.py --engine tpuf
  python scripts/reproduce_comparison.py --pinned
  python scripts/reproduce_comparison.py --resume results/reproduce-.../
  python scripts/reproduce_comparison.py --dry-run
"""

import argparse
import asyncio
import datetime
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
import numpy as np

try:
    import turbopuffer as tpuf
    from qdrant_client import AsyncQdrantClient, models
except ImportError:
    print("ERROR: activate the poetry venv first")
    sys.exit(1)

# ── Dataset paths ──────────────────────────────────────────────────────────────
BASE    = Path(__file__).parent.parent
DBPEDIA = BASE / "datasets/dbpedia-openai-100K-1536-angular/dbpedia_openai_100K"
HM      = BASE / "datasets/h-and-m-2048-angular/hnm"
MT      = BASE / "datasets/random-768-100-tenants/random_keywords_1m_768_vocab_100"

# ── Benchmark params ───────────────────────────────────────────────────────────
BATCH_SIZE         = 128
N_SEARCH           = 1000
N_WARMUP           = 1000
N_COLD             = 500
SEARCH_CONCURRENCY = [1, 8, 32]
FIXED_QPS_LEVELS   = [1, 5, 10, 20, 50]
FIXED_QPS_SECS     = 120
# --op sweep: concurrency sweep for the latency↔throughput Pareto frontier.
# Capped at p=32: the 2-CPU Qdrant node saturates by ~p=8–16, so p=32 already
# shows the bend-back; p=64 just drives server/client into overload+timeouts
# (queue-dominated data, not clean throughput). Write sweep is lighter still.
SWEEP_READ_CONCURRENCY  = [1, 2, 4, 8, 16, 32]
SWEEP_WRITE_CONCURRENCY = [1, 2, 4, 8, 16]
SWEEP_WRITE_N           = 10000   # vectors pushed per write-concurrency level
PINNED_REPLICAS    = 4
EF_SWEEP_DISK      = [32, 64, 128]
N_COLD_DISK        = 200
RW_POST_UPLOAD_S   = 120
RW_READ_INTERVAL   = 0.5

# Cost constants (DBpedia 100K×1536 only)
TPUF_COST_PER_QUERY    = 1.28 / 1_000_000
TPUF_STORAGE_MONTHLY   = 0.10
QDRANT_DBPEDIA_MONTHLY = 26.10
SECS_PER_MONTH         = 30 * 24 * 3600


# ── Dataset config ─────────────────────────────────────────────────────────────

@dataclass
class DatasetConfig:
    key: str
    label: str
    path: Path
    dims: int
    has_filter: bool         # tests.jsonl has "conditions"
    has_payload: bool        # payloads.jsonl exists
    tenant_field: Optional[str]  # MT: field for per-tenant routing
    tpuf_ns: str             # main namespace (prefix for MT)
    tpuf_ns_pinned: str      # pinned namespace
    tpuf_ns_rw: str          # write-read namespace
    qdrant_col: str
    qdrant_col_deferred: str
    qdrant_col_rw: str
    hnsw_m: int = 16
    hnsw_ef: int = 128


DATASETS: dict[str, DatasetConfig] = {
    "dbpedia": DatasetConfig(
        key="dbpedia", label="DBpedia 100K×1536", path=DBPEDIA, dims=1536,
        has_filter=False, has_payload=False, tenant_field=None,
        tpuf_ns="reproduce-dbpedia-100k-1536",
        tpuf_ns_pinned="reproduce-dbpedia-pinned-1r",
        tpuf_ns_rw="reproduce-dbpedia-rw",
        qdrant_col="reproduce-dbpedia",
        qdrant_col_deferred="reproduce-dbpedia-deferred-idx",
        qdrant_col_rw="reproduce-dbpedia-rw-qdrant",
    ),
    "hm": DatasetConfig(
        key="hm", label="H&M 105K×2048", path=HM, dims=2048,
        has_filter=True, has_payload=True, tenant_field=None,
        tpuf_ns="reproduce-hm-105k-2048",
        tpuf_ns_pinned="reproduce-hm-pinned-1r",
        tpuf_ns_rw="reproduce-hm-rw",
        qdrant_col="reproduce-hm",
        qdrant_col_deferred="reproduce-hm-deferred-idx",
        qdrant_col_rw="reproduce-hm-rw-qdrant",
    ),
    "mt": DatasetConfig(
        key="mt", label="Multi-tenant 1M×768", path=MT, dims=768,
        has_filter=False, has_payload=True, tenant_field="a",
        tpuf_ns="reproduce-mt-",          # prefix; append tenant value
        tpuf_ns_pinned="",                # MT has no single pinned namespace
        tpuf_ns_rw="reproduce-mt-rw",     # single ns for write-read test
        qdrant_col="reproduce-multitenant",
        qdrant_col_deferred="",
        qdrant_col_rw="reproduce-mt-rw-qdrant",
    ),
}


# ── Experiment matrix ──────────────────────────────────────────────────────────
# Variants with "pinned" in name require --pinned.
# Variants with "deferred" use deferred HNSW indexing.
# Variants with "disk" use disk-backed Qdrant storage.

MATRIX: dict[str, dict[str, list[str]]] = {
    "dbpedia": {
        "upload":      ["tpuf", "tpuf_pinned_1r", "qdrant", "qdrant_deferred"],
        "search":      ["tpuf", "tpuf_pinned_4r", "qdrant"],
        "sweep":       ["tpuf", "qdrant"],
        "search_cold": ["tpuf_pinned_4r", "qdrant"],
        "fixed_qps":   ["tpuf", "qdrant"],
        "write_read":  ["tpuf", "qdrant"],
        "disk":        ["qdrant_disk_vec", "qdrant_disk_all"],
    },
    "hm": {
        "upload":      ["tpuf", "tpuf_pinned_1r", "qdrant", "qdrant_deferred"],
        "search":      ["tpuf", "tpuf_pinned_4r", "qdrant"],
        "sweep":       ["tpuf", "qdrant"],
        "search_cold": ["tpuf_pinned_4r", "qdrant"],
        "fixed_qps":   ["tpuf", "qdrant"],
        "write_read":  ["tpuf", "qdrant"],
    },
    "mt": {
        "upload":    ["tpuf", "qdrant"],
        "search":    ["tpuf", "qdrant"],
        "sweep":     ["tpuf", "qdrant"],
        "fixed_qps": ["tpuf", "qdrant"],
        "write_read": ["tpuf", "qdrant"],
    },
}

OP_ORDER = ["upload", "search", "sweep", "search_cold", "fixed_qps", "write_read", "disk"]

PHASES = (
    ["delete"] +
    [f"{ds}/{op}" for ds in MATRIX for op in OP_ORDER if op in MATRIX[ds]]
)


# ── Variant helpers ────────────────────────────────────────────────────────────

def _is_pinned(v: str) -> bool:
    return "pinned" in v


def _active_variants(ds_key: str, op: str, args) -> list[str]:
    all_v = MATRIX[ds_key][op]
    result = []
    for v in all_v:
        if _is_pinned(v) and not args.pinned:
            continue
        if args.engine and not any(v.startswith(e) for e in args.engine):
            continue
        result.append(v)
    return result


# ── State management ───────────────────────────────────────────────────────────
# Key per variant: "dbpedia/upload/tpuf", "hm/search/qdrant", etc.

def load_state(run_dir: Path) -> dict:
    p = run_dir / "state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_state(run_dir: Path, state: dict):
    (run_dir / "state.json").write_text(json.dumps(state, indent=2))


def _vkey(ds: str, op: str, variant: str) -> str:
    return f"{ds}/{op}/{variant}"


def is_variant_done(state: dict, ds: str, op: str, variant: str) -> bool:
    return state.get(_vkey(ds, op, variant), {}).get("status") == "done"


def mark_variant_done(run_dir: Path, state: dict, ds: str, op: str, variant: str, results: dict):
    key = _vkey(ds, op, variant)
    state[key] = {
        "status":  "done",
        "at":      time.strftime("%Y-%m-%dT%H:%M:%S"),
        "results": results,
    }
    save_state(run_dir, state)
    print(f"  [saved {key}]")


def all_variants_done(state: dict, ds: str, op: str, active: list[str]) -> bool:
    return bool(active) and all(is_variant_done(state, ds, op, v) for v in active)


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
        "p90_ms":  round(float(np.percentile(a, 90)), 1),
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

TS_MAX = 2000  # cap timeseries samples per phase (keeps all ~1000 search queries)

def _ts(cols, rows):
    """Compact per-request/per-batch timeseries, uniformly downsampled to <=TS_MAX rows.
    Consumed by the report's timeseries mode (latency/WPS/recall over wall-clock)."""
    if len(rows) > TS_MAX:
        step = len(rows) / TS_MAX
        rows = [rows[int(i * step)] for i in range(TS_MAX)]
    return {"cols": cols, "rows": rows}


def _upload_stats(total, batch_lats, t_total):
    batch_lats_arr = np.array(batch_lats)
    wps = round(total / t_total, 1)
    return {
        "total_s":      round(t_total, 1),
        "wps":          wps,
        "batch_p50_ms": round(float(np.percentile(batch_lats_arr, 50)) * 1000, 1),
        "batch_p90_ms": round(float(np.percentile(batch_lats_arr, 90)) * 1000, 1),
        "batch_p99_ms": round(float(np.percentile(batch_lats_arr, 99)) * 1000, 1),
    }


async def tpuf_upload(ns, ids, vectors, extra_cols=None, _return_raw_lats=False):
    """Upload vectors to a tpuf namespace in batches.

    When _return_raw_lats=True returns (stats_dict, raw_batch_lats) so callers
    like MT upload can aggregate latencies correctly across tenants.
    """
    total = len(ids)
    t0 = time.perf_counter()
    batch_lats = []
    server_ms_list = []
    billable_bytes = 0
    ts_rows = []
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        cols = {"id": ids[start:end], "vector": vectors[start:end].tolist()}
        if extra_cols:
            for k, v in extra_cols.items():
                cols[k] = v[start:end]
        bt = time.perf_counter()
        resp = await ns.write(upsert_columns=cols, distance_metric="cosine_distance")
        bl = time.perf_counter() - bt
        batch_lats.append(bl)
        ts_rows.append([round(time.perf_counter() - t0, 2), round(bl * 1000, 1), end])
        if resp.performance:
            server_ms_list.append(resp.performance.server_total_ms)
        if resp.billing:
            billable_bytes += resp.billing.billable_logical_bytes_written
        if (start // BATCH_SIZE) % 20 == 0:
            print(f"    tpuf {end}/{total}", flush=True)
    s = _upload_stats(total, batch_lats, time.perf_counter() - t0)
    s["timeseries"] = _ts(["t_s", "batch_ms", "vectors"], ts_rows)
    if server_ms_list:
        arr = np.array(server_ms_list)
        s["server_p50_ms"] = round(float(np.percentile(arr, 50)), 1)
        s["server_p90_ms"] = round(float(np.percentile(arr, 90)), 1)
        s["server_p99_ms"] = round(float(np.percentile(arr, 99)), 1)
    if billable_bytes:
        s["billable_gb"] = round(billable_bytes / 1e9, 4)
    if _return_raw_lats:
        return s, batch_lats
    return s


async def qdrant_stored_gb(collection_name):
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


async def qdrant_upsert_timed(collection, points_dicts, client=None):
    """Upsert a batch. Pass `client` to reuse a pooled connection (avoids a
    fresh TCP+TLS handshake per batch); otherwise a throwaway client is used."""
    url = os.environ["QDRANT_CLUSTER_URL"].rstrip("/") + f"/collections/{collection}/points"
    api_key = os.environ.get("QDRANT_API_KEY")
    headers = {"api-key": api_key, "Content-Type": "application/json"} if api_key else {"Content-Type": "application/json"}
    if client is not None:
        resp = await client.put(url, json={"points": points_dicts}, headers=headers)
        resp.raise_for_status()
        return resp.json().get("time", 0) * 1000
    async with httpx.AsyncClient(timeout=120) as _c:
        resp = await _c.put(url, json={"points": points_dicts}, headers=headers)
        resp.raise_for_status()
    return resp.json().get("time", 0) * 1000


async def qdrant_upload(qc, collection, vectors, ids, payloads=None):
    total = len(ids)
    t0 = time.perf_counter()
    batch_lats = []
    server_ms_list = []
    ts_rows = []
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        points_dicts = [
            {"id": int(ids[start + i]), "vector": vec.tolist(),
             **({"payload": payloads[start + i]} if payloads else {})}
            for i, vec in enumerate(vectors[start:end])
        ]
        bt = time.perf_counter()
        server_ms = await qdrant_upsert_timed(collection, points_dicts)
        bl = time.perf_counter() - bt
        batch_lats.append(bl)
        ts_rows.append([round(time.perf_counter() - t0, 2), round(bl * 1000, 1), end])
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
    s["index_s"] = round(t_total - t_upsert, 1)
    s["total_s"] = round(t_total, 1)
    s["timeseries"] = _ts(["t_s", "batch_ms", "vectors"], ts_rows)
    if server_ms_list:
        arr = np.array(server_ms_list)
        s["server_p50_ms"] = round(float(np.percentile(arr, 50)), 1)
        s["server_p90_ms"] = round(float(np.percentile(arr, 90)), 1)
        s["server_p99_ms"] = round(float(np.percentile(arr, 99)), 1)
    stored_gb = await qdrant_stored_gb(collection)
    if stored_gb is not None:
        s["stored_gb"] = stored_gb
    return s


async def qdrant_upload_only(qc, collection, vectors, ids, payloads=None):
    total = len(ids)
    t0 = time.perf_counter()
    batch_lats = []
    server_ms_list = []
    ts_rows = []
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        points_dicts = [
            {"id": int(ids[start + i]), "vector": vec.tolist(),
             **({"payload": payloads[start + i]} if payloads else {})}
            for i, vec in enumerate(vectors[start:end])
        ]
        bt = time.perf_counter()
        server_ms = await qdrant_upsert_timed(collection, points_dicts)
        bl = time.perf_counter() - bt
        batch_lats.append(bl)
        ts_rows.append([round(time.perf_counter() - t0, 2), round(bl * 1000, 1), end])
        server_ms_list.append(server_ms)
        if (start // BATCH_SIZE) % 20 == 0:
            print(f"    qdrant {end}/{total}", flush=True)
    upsert_s = time.perf_counter() - t0
    s = _upload_stats(total, batch_lats, upsert_s)
    s["timeseries"] = _ts(["t_s", "batch_ms", "vectors"], ts_rows)
    if server_ms_list:
        arr = np.array(server_ms_list)
        s["server_p50_ms"] = round(float(np.percentile(arr, 50)), 1)
        s["server_p90_ms"] = round(float(np.percentile(arr, 90)), 1)
        s["server_p99_ms"] = round(float(np.percentile(arr, 99)), 1)
    stored_gb = await qdrant_stored_gb(collection)
    if stored_gb is not None:
        s["stored_gb"] = stored_gb
    return s


# ── Concurrent-write helpers (for the write-side concurrency sweep) ─────────────
# Fire batches with a semaphore of `concurrency` and report the measured
# aggregate WPS plus per-batch latency percentiles at that concurrency.

async def tpuf_write_at_concurrency(ns, ids, vectors, concurrency, extra_cols=None):
    sem = asyncio.Semaphore(concurrency)
    batch_lats = []
    starts = list(range(0, len(ids), BATCH_SIZE))

    async def one(start):
        end = min(start + BATCH_SIZE, len(ids))
        cols = {"id": ids[start:end], "vector": vectors[start:end].tolist()}
        if extra_cols:
            for k, v in extra_cols.items():
                cols[k] = v[start:end]
        async with sem:
            bt = time.perf_counter()
            await ns.write(upsert_columns=cols, distance_metric="cosine_distance")
            batch_lats.append(time.perf_counter() - bt)

    t0 = time.perf_counter()
    await asyncio.gather(*[one(s) for s in starts])
    dur = time.perf_counter() - t0
    arr = np.array(batch_lats) * 1000
    return {
        "concurrency":  concurrency,
        "wps_measured": round(len(ids) / dur, 1),
        "batch_p50_ms": round(float(np.percentile(arr, 50)), 1),
        "batch_p99_ms": round(float(np.percentile(arr, 99)), 1),
    }


async def qdrant_write_at_concurrency(collection, ids, vectors, concurrency, payloads=None):
    sem = asyncio.Semaphore(concurrency)
    batch_lats = []
    starts = list(range(0, len(ids), BATCH_SIZE))
    # One pooled client for the whole level so batches reuse keep-alive
    # connections instead of a fresh TCP+TLS handshake each (which capped
    # the low-concurrency end and understated sustained write throughput).
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)

    async with httpx.AsyncClient(timeout=120, limits=limits) as client:
        async def one(start):
            end = min(start + BATCH_SIZE, len(ids))
            pts = [
                {"id": int(ids[start + i]), "vector": vec.tolist(),
                 **({"payload": payloads[start + i]} if payloads else {})}
                for i, vec in enumerate(vectors[start:end])
            ]
            async with sem:
                bt = time.perf_counter()
                await qdrant_upsert_timed(collection, pts, client=client)
                batch_lats.append(time.perf_counter() - bt)

        t0 = time.perf_counter()
        await asyncio.gather(*[one(s) for s in starts])
        dur = time.perf_counter() - t0
    arr = np.array(batch_lats) * 1000
    return {
        "concurrency":  concurrency,
        "wps_measured": round(len(ids) / dur, 1),
        "batch_p50_ms": round(float(np.percentile(arr, 50)), 1),
        "batch_p99_ms": round(float(np.percentile(arr, 99)), 1),
    }


async def _ensure_qdrant_sweep_col(qc, col, ds):
    """Create the scratch sweep collection if absent (never deletes existing)."""
    existing = [c.name for c in (await qc.get_collections()).collections]
    if col in existing:
        return
    await qc.create_collection(
        collection_name=col,
        vectors_config=models.VectorParams(size=ds.dims, distance=models.Distance.COSINE),
        hnsw_config=models.HnswConfigDiff(m=ds.hnsw_m, ef_construct=ds.hnsw_ef),
        optimizers_config=models.OptimizersConfigDiff(memmap_threshold=10_000_000),
    )


async def qdrant_trigger_and_wait_index(qc, collection, total_vectors, indexing_threshold=20000, poll_interval=2):
    print(f"  Enabling HNSW indexing (indexing_threshold={indexing_threshold})...", flush=True)
    await qc.update_collection(
        collection_name=collection,
        optimizers_config=models.OptimizersConfigDiff(indexing_threshold=indexing_threshold),
    )
    t0 = time.perf_counter()
    poll_rows = []
    while True:
        info = await qc.get_collection(collection)
        t_s = round(time.perf_counter() - t0, 1)
        indexed = info.indexed_vectors_count or 0
        poll_rows.append([t_s, indexed])
        pct = f"{indexed/total_vectors*100:.1f}%" if total_vectors else "?"
        print(f"    t={t_s}s  indexed={indexed}/{total_vectors} ({pct})  status={info.status}", flush=True)
        if info.status == models.CollectionStatus.GREEN:
            break
        await asyncio.sleep(poll_interval)
    index_s = round(time.perf_counter() - t0, 1)
    final_indexed = poll_rows[-1][1] if poll_rows else 0
    return {
        "index_s":       index_s,
        "index_vps":     round(total_vectors / index_s, 1) if index_s > 0 else 0,
        "poll_rows":     poll_rows,
        "final_indexed": final_indexed,
    }


async def tpuf_poll_spfresh_index(ns, total_vectors, poll_interval=5, quiet=False):
    """Poll ns.metadata().index until status == 'up-to-date'.

    Uses the official index status endpoint rather than query-level
    exhaustive_search_count, which is query-dependent and not a reliable
    completion signal. Pass quiet=True to suppress per-poll logging (used
    when polling many namespaces concurrently, e.g. multi-tenant).
    """
    if not quiet:
        print("  Polling SPFresh build (index.status → up-to-date) ...", flush=True)
    t0 = time.perf_counter()
    poll_rows = []
    while True:
        meta = await ns.metadata()
        t_s  = round(time.perf_counter() - t0, 1)
        idx  = meta.index
        if idx.status == "up-to-date":
            poll_rows.append([t_s, 0])
            if not quiet:
                print(f"    t={t_s}s  status=up-to-date", flush=True)
            break
        unindexed_bytes = getattr(idx, "unindexed_bytes", -1)
        poll_rows.append([t_s, unindexed_bytes])
        if not quiet:
            print(f"    t={t_s}s  status=updating  unindexed_bytes={unindexed_bytes}", flush=True)
        await asyncio.sleep(poll_interval)
    return {"index_s": round(time.perf_counter() - t0, 1), "poll_rows": poll_rows}


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
    if not r.performance:
        return None
    return {
        "server_total_ms":         r.performance.server_total_ms,
        "query_execution_ms":      r.performance.query_execution_ms,
        "cache_hit_ratio":         r.performance.cache_hit_ratio,
        "cache_temperature":       r.performance.cache_temperature,
        "exhaustive_search_count": r.performance.exhaustive_search_count,
        "billable_bytes":          r.billing.billable_logical_bytes_queried if r.billing else None,
    }


async def run_search(query_fn, tests, concurrency, n=N_SEARCH, collect_perf=False):
    """Fire n queries at given concurrency. Errors are counted but don't abort."""
    sem = asyncio.Semaphore(concurrency)
    latencies = []
    returned  = [None] * n
    tpuf_perf_rows   = []
    qdrant_server_ms = []
    ts_rows = []          # per-query [t_s, lat_ms, server_ms] for timeseries mode
    n_errors = 0
    t_run0 = time.perf_counter()

    async def one(i, t):
        nonlocal n_errors
        async with sem:
            t0 = time.perf_counter()
            try:
                result = await query_fn(t["query"], t.get("conditions") or {})
                lat = time.perf_counter() - t0
                latencies.append(lat)
                srv = None
                if isinstance(result, tuple):
                    ids, meta = result
                    returned[i] = ids
                    if collect_perf and meta and isinstance(meta, dict):
                        tpuf_perf_rows.append(meta)
                        srv = meta.get("server_total_ms")
                    elif meta is not None and isinstance(meta, (int, float)):
                        qdrant_server_ms.append(meta)
                        srv = meta
                else:
                    returned[i] = result
                ts_rows.append([round(t0 - t_run0, 3), round(lat * 1000, 2),
                                round(srv, 2) if srv is not None else None])
            except Exception as e:
                n_errors += 1
                returned[i] = None  # None means error; [] means 0 results (valid)

    await asyncio.gather(*[one(i, tests[i % len(tests)]) for i in range(n)])
    dur = time.perf_counter() - t_run0

    s = stats(latencies)
    s["n_errors"] = n_errors
    # measured aggregate throughput (completed queries / wall-clock) — captures
    # saturation, unlike the p×(1/mean) derivation which overstates at the knee
    s["rps_measured"] = round((n - n_errors) / dur, 1) if dur > 0 else 0.0
    if ts_rows:
        ts_rows.sort(key=lambda r: r[0])
        s["timeseries"] = _ts(["t_s", "lat_ms", "server_ms"], ts_rows)
    valid_indices = [i for i in range(n) if returned[i] is not None]
    if valid_indices:
        recalls = [recall_at_k(returned[i], tests[i % len(tests)]["closest_ids"]) for i in valid_indices]
        s["recall_pct"] = round(float(np.mean(recalls)) * 100, 2)

    if tpuf_perf_rows:
        srv    = np.array([p["server_total_ms"]         for p in tpuf_perf_rows])
        exe    = np.array([p["query_execution_ms"]      for p in tpuf_perf_rows])
        hit    = np.array([p["cache_hit_ratio"]         for p in tpuf_perf_rows])
        billed = np.array([p["billable_bytes"] or 0     for p in tpuf_perf_rows])
        exh    = np.array([p["exhaustive_search_count"] for p in tpuf_perf_rows])
        s["tpuf_server_p50_ms"]  = round(float(np.percentile(srv, 50)), 1)
        s["tpuf_server_p90_ms"]  = round(float(np.percentile(srv, 90)), 1)
        s["tpuf_server_p99_ms"]  = round(float(np.percentile(srv, 99)), 1)
        s["tpuf_exec_p50_ms"]    = round(float(np.percentile(exe, 50)), 1)
        s["tpuf_exec_p99_ms"]    = round(float(np.percentile(exe, 99)), 1)
        s["tpuf_cache_hit_avg"]  = round(float(np.mean(hit)), 3)
        s["tpuf_billed_gb_avg"]  = round(float(np.mean(billed)) / 1e9, 6)
        s["tpuf_exhaustive_avg"] = round(float(np.mean(exh)), 1)
        temps = [p["cache_temperature"] for p in tpuf_perf_rows]
        s["tpuf_cache_temp"]     = max(set(temps), key=temps.count)
    if qdrant_server_ms:
        arr = np.array(qdrant_server_ms)
        s["qdrant_server_p50_ms"] = round(float(np.percentile(arr, 50)), 3)
        s["qdrant_server_p90_ms"] = round(float(np.percentile(arr, 90)), 3)
        s["qdrant_server_p99_ms"] = round(float(np.percentile(arr, 99)), 3)
    return s


async def fixed_qps_run(query_fn, qps: float, duration_s: int, server_ms_sink=None):
    """Dispatch queries at target QPS. Only successful queries count in latencies."""
    interval  = 1.0 / qps
    deadline  = time.monotonic() + duration_s
    latencies = []
    in_flight = set()

    async def one():
        t0 = time.perf_counter()
        try:
            result = await query_fn()
            latencies.append(time.perf_counter() - t0)  # only on success
            if server_ms_sink is not None and isinstance(result, (int, float)):
                server_ms_sink.append(result)
        except Exception:
            pass

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


# ── Query function builders ────────────────────────────────────────────────────

def _make_tpuf_qfn(ns, ds: DatasetConfig, ns_cache: dict, tc):
    """Build a tpuf query function for the given dataset."""
    if ds.tenant_field:
        async def qfn(vec, cond, _tc=tc, _cache=ns_cache):
            tv = cond.get("and", [{}])[0].get(ds.tenant_field, {}).get("match", {}).get("value")
            if not tv:
                raise ValueError(f"Missing tenant field '{ds.tenant_field}' in conditions: {cond}")
            if tv not in _cache:
                _cache[tv] = _tc.namespace(f"{ds.tpuf_ns}{tv}")
            r = await _cache[tv].query(rank_by=("vector", "ANN", vec), top_k=10, include_attributes=False)
            return ([x.id for x in r.rows], _tpuf_perf(r))
    else:
        async def qfn(vec, cond, _ns=ns):
            r = await _ns.query(
                rank_by=("vector", "ANN", vec), top_k=10,
                filters=to_tpuf_filter(cond) if ds.has_filter else None,
                include_attributes=False,
            )
            return ([x.id for x in r.rows], _tpuf_perf(r))
    return qfn


def _make_qdrant_qfn(qc, collection: str, ds: DatasetConfig, hnsw_ef: int = 128):
    """Build a Qdrant query function for the given dataset."""
    async def qfn(vec, cond, _qc=qc, _col=collection, _ef=hnsw_ef):
        raw = await _qc.http.search_api.query_points(
            collection_name=_col,
            query_request=models.QueryRequest(
                query=vec,
                filter=to_qdrant_filter(cond) if cond else None,
                params=models.SearchParams(hnsw_ef=_ef),
                limit=10, with_vector=False, with_payload=False,
            ),
        )
        return ([pt.id for pt in raw.result.points], raw.time * 1000)
    return qfn


# ── MT upload helper ───────────────────────────────────────────────────────────

async def _mt_tpuf_upload(tc, vecs, payloads, ids, ds: DatasetConfig) -> dict:
    """Upload MT dataset to per-tenant namespaces in parallel. Fixes the
    percentile-of-percentiles bug by collecting raw batch latencies across tenants."""
    tenants = sorted(set(p[ds.tenant_field] for p in payloads))
    groups  = {t: [i for i, p in enumerate(payloads) if p[ds.tenant_field] == t] for t in tenants}

    sem = asyncio.Semaphore(10)
    t0 = time.perf_counter()
    all_batch_lats: list[float] = []
    all_billable_gb: list[float] = []

    async def upload_tenant(tenant_val):
        async with sem:
            idxs = groups[tenant_val]
            s, raw_lats = await tpuf_upload(
                tc.namespace(f"{ds.tpuf_ns}{tenant_val}"),
                [ids[i] for i in idxs],
                vecs[idxs],
                _return_raw_lats=True,
            )
            all_batch_lats.extend(raw_lats)
            if "billable_gb" in s:
                all_billable_gb.append(s["billable_gb"])

    await asyncio.gather(*[upload_tenant(t) for t in tenants])
    wall_s = time.perf_counter() - t0
    total_vecs = len(ids)
    result = {
        "total_s":  round(wall_s, 1),
        "wps":      round(total_vecs / wall_s, 1),
        "n_tenants": len(tenants),
    }
    if all_batch_lats:
        arr = np.array(all_batch_lats) * 1000
        result["batch_p50_ms"] = round(float(np.percentile(arr, 50)), 1)
        result["batch_p90_ms"] = round(float(np.percentile(arr, 90)), 1)
        result["batch_p99_ms"] = round(float(np.percentile(arr, 99)), 1)
    if all_billable_gb:
        result["billable_gb"] = round(sum(all_billable_gb), 4)

    # SPFresh build across all tenant namespaces — poll each concurrently and
    # report the distribution (max = wall-clock until every namespace is indexed).
    print(f"  Polling SPFresh across {len(tenants)} tenant namespaces ...", flush=True)
    sem_idx = asyncio.Semaphore(20)
    per_ns_s: list[float] = []
    t_idx0 = time.perf_counter()

    async def poll_tenant(tenant_val):
        async with sem_idx:
            r = await tpuf_poll_spfresh_index(
                tc.namespace(f"{ds.tpuf_ns}{tenant_val}"), len(groups[tenant_val]), quiet=True)
            per_ns_s.append(r["index_s"])

    await asyncio.gather(*[poll_tenant(t) for t in tenants])
    if per_ns_s:
        a = np.array(per_ns_s)
        result["spfresh_index_s"]     = round(time.perf_counter() - t_idx0, 1)  # until all indexed
        result["spfresh_per_ns_p50_s"] = round(float(np.percentile(a, 50)), 1)
        result["spfresh_per_ns_p90_s"] = round(float(np.percentile(a, 90)), 1)
        result["spfresh_per_ns_max_s"] = round(float(a.max()), 1)
        print(f"  MT SPFresh: all indexed in {result['spfresh_index_s']}s  "
              f"(per-ns p50={result['spfresh_per_ns_p50_s']}s  max={result['spfresh_per_ns_max_s']}s)", flush=True)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# OP: upload
# ═══════════════════════════════════════════════════════════════════════════════

async def op_upload(ds: DatasetConfig, active: list[str], run_dir: Path, state: dict, args):
    print(f"\n═══ {ds.key}/upload  variants={active} ═══")

    vecs  = np.load(ds.path / "vectors.npy")
    ids   = list(range(len(vecs)))
    tests = [json.loads(l) for l in open(ds.path / "tests.jsonl")]
    test_vec = tests[0]["query"]
    print(f"  {vecs.shape[0]} × {vecs.shape[1]}, batch={BATCH_SIZE}")

    payloads    = None
    extra_cols  = None
    filter_fields: list[str] = []
    if ds.has_payload and not ds.tenant_field:
        payloads = [json.loads(l) for l in open(ds.path / "payloads.jsonl")]
        fmeta    = json.loads((ds.path / "filters.json").read_text())
        filter_fields = [f["name"] for f in fmeta]
        extra_cols = {f: [p.get(f) for p in payloads] for f in filter_fields}
    elif ds.tenant_field:
        payloads = [json.loads(l) for l in open(ds.path / "payloads.jsonl")]

    # ── tpuf serverless ───────────────────────────────────────────────────────
    if "tpuf" in active and not is_variant_done(state, ds.key, "upload", "tpuf"):
        tc = make_tpuf()
        ns = tc.namespace(ds.tpuf_ns) if not ds.tenant_field else None
        if ds.tenant_field:
            up = await _mt_tpuf_upload(tc, vecs, payloads, ids, ds)
            print(f"  tpuf MT: {up['total_s']/60:.1f}min  wps={up['wps']}  tenants={up['n_tenants']}")
            mark_variant_done(run_dir, state, ds.key, "upload", "tpuf", up)
        else:
            up  = await tpuf_upload(ns, ids, vecs, extra_cols=extra_cols)
            idx = await tpuf_poll_spfresh_index(ns, len(ids))
            print(f"  tpuf: upload={up['total_s']/60:.1f}min  SPFresh={idx['index_s']/60:.2f}min  total={(up['total_s']+idx['index_s'])/60:.1f}min  wps={up['wps']}")
            mark_variant_done(run_dir, state, ds.key, "upload", "tpuf",
                              {**up, "spfresh_index_s": idx["index_s"], "spfresh_poll_rows": idx["poll_rows"]})

    # ── tpuf pinned 1r ────────────────────────────────────────────────────────
    if "tpuf_pinned_1r" in active and not is_variant_done(state, ds.key, "upload", "tpuf_pinned_1r"):
        if ds.tenant_field:
            print("  skip tpuf_pinned_1r (not applicable for MT)")
        else:
            tc   = make_tpuf()
            ns_p = tc.namespace(ds.tpuf_ns_pinned)
            seed = {"id": ids[:BATCH_SIZE], "vector": vecs[:BATCH_SIZE].tolist()}
            if extra_cols:
                for k, v in extra_cols.items():
                    seed[k] = v[:BATCH_SIZE]
            await ns_p.write(upsert_columns=seed, distance_metric="cosine_distance")
            await pin_and_wait(ns_p, replicas=1)
            up  = await tpuf_upload(ns_p, ids, vecs, extra_cols=extra_cols)
            idx = await tpuf_poll_spfresh_index(ns_p, len(ids))
            await unpin(ns_p)
            print(f"  tpuf pinned-1r: upload={up['total_s']/60:.1f}min  SPFresh={idx['index_s']/60:.2f}min  wps={up['wps']}")
            mark_variant_done(run_dir, state, ds.key, "upload", "tpuf_pinned_1r",
                              {**up, "spfresh_index_s": idx["index_s"], "spfresh_poll_rows": idx["poll_rows"]})

    # ── qdrant concurrent ─────────────────────────────────────────────────────
    if "qdrant" in active and not is_variant_done(state, ds.key, "upload", "qdrant"):
        qc = make_qdrant()
        if ds.tenant_field:
            hnsw_cfg = models.HnswConfigDiff(m=0, payload_m=16)
        else:
            hnsw_cfg = models.HnswConfigDiff(m=ds.hnsw_m, ef_construct=ds.hnsw_ef)
        try:
            await qc.delete_collection(ds.qdrant_col)
        except Exception:
            pass
        await qc.create_collection(
            collection_name=ds.qdrant_col,
            vectors_config=models.VectorParams(size=ds.dims, distance=models.Distance.COSINE),
            hnsw_config=hnsw_cfg,
            optimizers_config=models.OptimizersConfigDiff(memmap_threshold=10_000_000),
        )
        for field in filter_fields:
            await qc.create_payload_index(ds.qdrant_col, field, models.PayloadSchemaType.KEYWORD)
        if ds.tenant_field:
            await qc.create_payload_index(
                ds.qdrant_col, ds.tenant_field,
                models.KeywordIndexParams(type="keyword", is_tenant=True),
            )
        qt = await qdrant_upload(qc, ds.qdrant_col, vecs, ids, payloads=payloads)
        await qc.close()
        print(f"  qdrant: upsert={(qt['total_s']-qt['index_s'])/60:.1f}min  index={qt['index_s']/60:.1f}min  total={qt['total_s']/60:.1f}min  wps={qt['wps']}")
        mark_variant_done(run_dir, state, ds.key, "upload", "qdrant", qt)

    # ── qdrant deferred ───────────────────────────────────────────────────────
    if "qdrant_deferred" in active and not is_variant_done(state, ds.key, "upload", "qdrant_deferred"):
        if not ds.qdrant_col_deferred:
            print(f"  skip qdrant_deferred (not configured for {ds.key})")
        else:
            qc = make_qdrant()
            try:
                await qc.delete_collection(ds.qdrant_col_deferred)
            except Exception:
                pass
            await qc.create_collection(
                collection_name=ds.qdrant_col_deferred,
                vectors_config=models.VectorParams(size=ds.dims, distance=models.Distance.COSINE),
                hnsw_config=models.HnswConfigDiff(m=ds.hnsw_m, ef_construct=ds.hnsw_ef),
                optimizers_config=models.OptimizersConfigDiff(indexing_threshold=0, memmap_threshold=10_000_000),
            )
            for field in filter_fields:
                await qc.create_payload_index(ds.qdrant_col_deferred, field, models.PayloadSchemaType.KEYWORD)
            qt_up  = await qdrant_upload_only(qc, ds.qdrant_col_deferred, vecs, ids, payloads=payloads)
            qt_idx = await qdrant_trigger_and_wait_index(qc, ds.qdrant_col_deferred, len(ids))
            await qc.close()
            total_s = round(qt_up["total_s"] + qt_idx["index_s"], 1)
            print(f"  qdrant deferred: upsert={qt_up['total_s']/60:.2f}min  HNSW={qt_idx['index_s']/60:.2f}min  total={total_s/60:.2f}min")
            mark_variant_done(run_dir, state, ds.key, "upload", "qdrant_deferred",
                              {"upsert": qt_up, "indexing": qt_idx, "total_s": total_s})

    # Print summary of what's in state
    print(f"\n  ┌─ Upload summary: {ds.label}")
    for v in ["tpuf", "tpuf_pinned_1r", "qdrant", "qdrant_deferred"]:
        if not is_variant_done(state, ds.key, "upload", v):
            continue
        r = state[_vkey(ds.key, "upload", v)]["results"]
        if v.startswith("tpuf"):
            if "total_s" in r and "spfresh_index_s" in r:
                total = (r["total_s"] + r["spfresh_index_s"]) / 60
                print(f"  │  {v:20s}  total={total:.1f}min  upload={r['total_s']/60:.1f}min  SPFresh={r['spfresh_index_s']/60:.1f}min  wps={r.get('wps','?')}")
            elif "total_s" in r:
                print(f"  │  {v:20s}  total={r['total_s']/60:.1f}min  wps={r.get('wps','?')}")
        elif v == "qdrant":
            print(f"  │  {v:20s}  total={r.get('total_s',0)/60:.1f}min  upsert={(r.get('total_s',0)-r.get('index_s',0))/60:.1f}min  index={r.get('index_s',0)/60:.1f}min  wps={r.get('wps','?')}")
        elif v == "qdrant_deferred":
            print(f"  │  {v:20s}  total={r.get('total_s',0)/60:.1f}min  upsert={r['upsert'].get('total_s',0)/60:.1f}min  HNSW={r['indexing'].get('index_s',0)/60:.1f}min")
    print(f"  └─")


# ═══════════════════════════════════════════════════════════════════════════════
# OP: search
# ═══════════════════════════════════════════════════════════════════════════════

async def op_search(ds: DatasetConfig, active: list[str], run_dir: Path, state: dict, args):
    print(f"\n═══ {ds.key}/search  variants={active} ═══")
    tests    = [json.loads(l) for l in open(ds.path / "tests.jsonl")]
    tc       = make_tpuf()
    qc       = make_qdrant()
    ns_cache = {}

    for variant in active:
        if is_variant_done(state, ds.key, "search", variant):
            print(f"  skip {variant} (done)")
            continue
        print(f"\n  ── {variant} ──")
        pinned_ns = None
        try:
            if variant == "tpuf_pinned_4r":
                pinned_ns = tc.namespace(ds.tpuf_ns)
                ok = await pin_and_wait(pinned_ns, replicas=PINNED_REPLICAS)
                if not ok:
                    print(f"  ERROR: pin timeout for {variant}, skipping")
                    continue

            ns = pinned_ns if pinned_ns else tc.namespace(ds.tpuf_ns)
            is_tpuf = variant.startswith("tpuf")
            coll = ds.qdrant_col

            # Warmup
            print(f"  warming {N_WARMUP} queries p=1 ...", flush=True)
            if is_tpuf:
                qfn = _make_tpuf_qfn(ns, ds, ns_cache, tc)
            else:
                qfn = _make_qdrant_qfn(qc, coll, ds)
            await run_search(qfn, tests[:N_WARMUP], concurrency=1)

            results = {}
            for p in SEARCH_CONCURRENCY:
                s = await run_search(qfn, tests, concurrency=p, collect_perf=is_tpuf)
                results[f"p{p}"] = s
                pstats(f"{variant} p={p}", s, f"recall={s.get('recall_pct','?')}%")

            mark_variant_done(run_dir, state, ds.key, "search", variant, results)
        finally:
            if pinned_ns:
                await unpin(pinned_ns)

    await qc.close()

    print(f"\n  ┌─ Search summary: {ds.label}")
    print(f"  │  {'Variant':30s}  {'p':>3}  {'RPS':>7}  {'p50':>8}  {'p99':>8}  {'recall':>7}")
    for v in active:
        if not is_variant_done(state, ds.key, "search", v):
            continue
        r = state[_vkey(ds.key, "search", v)]["results"]
        for p in SEARCH_CONCURRENCY:
            s = r.get(f"p{p}", {})
            if s:
                print(f"  │  {v:30s}  {p:>3}  {s.get('rps',0):>7.1f}  {s.get('p50_ms',0):>7.1f}ms  {s.get('p99_ms',0):>7.1f}ms  {s.get('recall_pct','?'):>6}%")
    print(f"  └─")


# ═══════════════════════════════════════════════════════════════════════════════
# OP: sweep  — dense concurrency sweep (read + write) for the Pareto frontier
# ═══════════════════════════════════════════════════════════════════════════════

async def op_sweep(ds: DatasetConfig, active: list[str], run_dir: Path, state: dict, args):
    print(f"\n═══ {ds.key}/sweep  variants={active} ═══")
    vecs  = np.load(ds.path / "vectors.npy")
    ids   = list(range(len(vecs)))
    tests = [json.loads(l) for l in open(ds.path / "tests.jsonl")]

    payloads = None
    extra_cols = None
    if ds.has_payload and not ds.tenant_field:
        payloads = [json.loads(l) for l in open(ds.path / "payloads.jsonl")]
        fmeta    = json.loads((ds.path / "filters.json").read_text())
        ffields  = [f["name"] for f in fmeta]
        extra_cols = {f: [p.get(f) for p in payloads] for f in ffields}

    tc = make_tpuf()
    qc = make_qdrant()
    ns_cache = {}
    wn = min(SWEEP_WRITE_N, len(ids))

    for variant in active:
        if is_variant_done(state, ds.key, "sweep", variant):
            print(f"  skip {variant} (done)")
            continue
        print(f"\n  ── {variant} ──")
        is_tpuf = variant.startswith("tpuf")

        # READ sweep — against the main populated target (needs a prior upload)
        if is_tpuf:
            qfn = _make_tpuf_qfn(tc.namespace(ds.tpuf_ns), ds, ns_cache, tc)
        else:
            qfn = _make_qdrant_qfn(qc, ds.qdrant_col, ds)
        print(f"  warming {N_WARMUP} queries ...", flush=True)
        await run_search(qfn, tests[:N_WARMUP], concurrency=1)
        read_rows = []
        for p in SWEEP_READ_CONCURRENCY:
            s = await run_search(qfn, tests, concurrency=p, collect_perf=is_tpuf)
            read_rows.append({"p": p, "rps_measured": s.get("rps_measured"),
                              "p50_ms": s.get("p50_ms"), "p90_ms": s.get("p90_ms"),
                              "p99_ms": s.get("p99_ms"), "recall_pct": s.get("recall_pct"),
                              "n_errors": s.get("n_errors")})
            print(f"    read  p={p:<3} rps={s.get('rps_measured'):>7}  "
                  f"p50={s.get('p50_ms')}ms  p99={s.get('p99_ms')}ms  err={s.get('n_errors')}", flush=True)

        # WRITE sweep — dedicated scratch target so the main data is untouched
        write_rows = []
        if ds.tenant_field:
            print("  skip write sweep (MT per-tenant not supported)")
        else:
            ec = {k: v[:wn] for k, v in extra_cols.items()} if extra_cols else None
            if not is_tpuf:
                await _ensure_qdrant_sweep_col(qc, ds.qdrant_col + "-sweep", ds)
            for p in SWEEP_WRITE_CONCURRENCY:
                if is_tpuf:
                    w = await tpuf_write_at_concurrency(
                        tc.namespace(ds.tpuf_ns + "-sweep"), ids[:wn], vecs[:wn], p, extra_cols=ec)
                else:
                    w = await qdrant_write_at_concurrency(
                        ds.qdrant_col + "-sweep", ids[:wn], vecs[:wn], p,
                        payloads=payloads[:wn] if payloads else None)
                write_rows.append(w)
                print(f"    write p={p:<3} wps={w['wps_measured']:>7}  "
                      f"batch_p50={w['batch_p50_ms']}ms  batch_p99={w['batch_p99_ms']}ms", flush=True)

        mark_variant_done(run_dir, state, ds.key, "sweep", variant,
                          {"read": read_rows, "write": write_rows, "write_n": wn})

    await qc.close()
    print(f"\n  └─ sweep done: {ds.label}")


# ═══════════════════════════════════════════════════════════════════════════════
# OP: search_cold
# ═══════════════════════════════════════════════════════════════════════════════

async def op_search_cold(ds: DatasetConfig, active: list[str], run_dir: Path, state: dict, args):
    print(f"\n═══ {ds.key}/search_cold  variants={active} ═══")
    if ds.tenant_field:
        print("  skip search_cold (not applicable for MT)")
        return
    tests = [json.loads(l) for l in open(ds.path / "tests.jsonl")]
    tc    = make_tpuf()
    qc    = make_qdrant()

    # ── tpuf_pinned_4r cold ───────────────────────────────────────────────────
    if "tpuf_pinned_4r" in active and not is_variant_done(state, ds.key, "search_cold", "tpuf_pinned_4r"):
        cold_name = f"{ds.tpuf_ns}-cold"
        cold_ns   = tc.namespace(cold_name)
        try:
            try:
                await cold_ns.delete_all()
                print(f"  cleared stale {cold_name}")
            except Exception:
                pass
            print(f"  copying {ds.tpuf_ns} → {cold_name} (guaranteed cold) ...", flush=True)
            await cold_ns.copy_from(source_namespace=ds.tpuf_ns)
            await asyncio.sleep(3)
            ok = await pin_and_wait(cold_ns, replicas=PINNED_REPLICAS)
            if not ok:
                print(f"  ERROR: pin timeout for tpuf_pinned_4r cold, skipping")
                mark_variant_done(run_dir, state, ds.key, "search_cold", "tpuf_pinned_4r",
                                  {"error": "pin_timeout"})
                return

            qfn = _make_tpuf_qfn(cold_ns, ds, {}, tc)
            s   = await run_search(qfn, tests, concurrency=32, n=N_COLD, collect_perf=True)
            pstats(f"tpuf_pinned_4r cold p=32", s, f"recall={s.get('recall_pct','?')}%  cache={s.get('tpuf_cache_temp','?')}")
            mark_variant_done(run_dir, state, ds.key, "search_cold", "tpuf_pinned_4r",
                              {"p32_cold": s})
        finally:
            await unpin(cold_ns)
            try:
                await cold_ns.delete_all()
                print(f"  cleaned up {cold_name}")
            except Exception:
                pass

    # ── qdrant warm reference ─────────────────────────────────────────────────
    if "qdrant" in active and not is_variant_done(state, ds.key, "search_cold", "qdrant"):
        print("  qdrant: no cold-start (HNSW in RAM) — running warm reference at p=32")
        qfn = _make_qdrant_qfn(qc, ds.qdrant_col, ds)
        s   = await run_search(qfn, tests, concurrency=32)
        pstats("qdrant p=32 (warm reference)", s, f"recall={s.get('recall_pct','?')}%")
        mark_variant_done(run_dir, state, ds.key, "search_cold", "qdrant", {"p32_warm_ref": s})

    await qc.close()


# ═══════════════════════════════════════════════════════════════════════════════
# OP: fixed_qps
# ═══════════════════════════════════════════════════════════════════════════════

async def op_fixed_qps(ds: DatasetConfig, active: list[str], run_dir: Path, state: dict, args):
    print(f"\n═══ {ds.key}/fixed_qps  variants={active} ═══")
    tests  = [json.loads(l) for l in open(ds.path / "tests.jsonl")]
    vecs   = [t["query"] for t in tests]
    tc     = make_tpuf()
    qc     = make_qdrant()
    ns     = tc.namespace(ds.tpuf_ns)
    ns_cache: dict = {}

    for variant in active:
        if is_variant_done(state, ds.key, "fixed_qps", variant):
            print(f"  skip {variant} (done)")
            continue
        print(f"\n  ── {variant} ──")
        is_tpuf = variant.startswith("tpuf")
        results = {}

        for qps in FIXED_QPS_LEVELS:
            print(f"  QPS={qps} ({FIXED_QPS_SECS}s) ...", flush=True)
            srv_ms: list[float] = []
            idx = [0]

            if is_tpuf:
                if ds.tenant_field:
                    async def qfn(_tc=tc, _vecs=vecs, _idx=idx, _cache=ns_cache):
                        vec = _vecs[_idx[0] % len(_vecs)]
                        test = tests[_idx[0] % len(tests)]
                        _idx[0] += 1
                        tv = test.get("conditions", {}).get("and", [{}])[0].get(ds.tenant_field, {}).get("match", {}).get("value")
                        if tv and tv not in _cache:
                            _cache[tv] = _tc.namespace(f"{ds.tpuf_ns}{tv}")
                        ns_q = _cache.get(tv, _tc.namespace(ds.tpuf_ns))
                        r = await ns_q.query(rank_by=("vector", "ANN", vec), top_k=10, include_attributes=False)
                        return r.performance.server_total_ms if r.performance else 0
                else:
                    async def qfn(_ns=ns, _vecs=vecs, _idx=idx, _ds=ds):
                        vec = _vecs[_idx[0] % len(_vecs)]
                        _idx[0] += 1
                        r = await _ns.query(rank_by=("vector", "ANN", vec), top_k=10, include_attributes=False)
                        return r.performance.server_total_ms if r.performance else 0
            else:
                async def qfn(_qc=qc, _vecs=vecs, _idx=idx, _ds=ds):
                    vec = _vecs[_idx[0] % len(_vecs)]
                    cond = tests[_idx[0] % len(tests)].get("conditions") or {}
                    _idx[0] += 1
                    raw = await _qc.http.search_api.query_points(
                        collection_name=_ds.qdrant_col,
                        query_request=models.QueryRequest(
                            query=vec,
                            filter=to_qdrant_filter(cond) if cond else None,
                            params=models.SearchParams(hnsw_ef=128),
                            limit=10, with_vector=False, with_payload=False,
                        ),
                    )
                    return raw.time * 1000

            lats = await fixed_qps_run(qfn, qps, FIXED_QPS_SECS, server_ms_sink=srv_ms)
            s = stats(lats)
            if ds.key == "dbpedia" and is_tpuf:
                s["monthly_usd"] = round(TPUF_STORAGE_MONTHLY + qps * SECS_PER_MONTH * TPUF_COST_PER_QUERY, 2)
            elif ds.key == "dbpedia" and not is_tpuf:
                s["monthly_usd"] = QDRANT_DBPEDIA_MONTHLY
            if srv_ms:
                arr = np.array(srv_ms)
                s["server_p50_ms"] = round(float(np.percentile(arr, 50)), 1)
                s["server_p90_ms"] = round(float(np.percentile(arr, 90)), 1)
                s["server_p99_ms"] = round(float(np.percentile(arr, 99)), 1)
            results[f"qps{qps}"] = s
            extra = f"→ ${s['monthly_usd']:.2f}/mo" if "monthly_usd" in s else ""
            pstats(f"  {variant} @ {qps} QPS", s, extra)

        mark_variant_done(run_dir, state, ds.key, "fixed_qps", variant, results)

    await qc.close()


# ═══════════════════════════════════════════════════════════════════════════════
# OP: write_read  (each engine variant runs separately — no cross-engine contention)
# ═══════════════════════════════════════════════════════════════════════════════

async def _run_write_read_tpuf(ds: DatasetConfig, vecs, ids, tests, run_dir, state, args):
    """Concurrent write+read for tpuf — one namespace, writers and readers in parallel."""
    t0 = time.perf_counter()
    write_events: list[dict] = []
    read_events:  list[dict] = []
    upload_done  = False
    upload_end_t = 0.0
    stop_event   = asyncio.Event()

    tc = make_tpuf()
    ns_rw = tc.namespace(ds.tpuf_ns_rw)
    try:
        await ns_rw.delete_all()
        print(f"  tpuf: cleared {ds.tpuf_ns_rw}")
    except Exception:
        pass

    async def writer():
        nonlocal upload_done, upload_end_t
        try:
            written = 0
            for start in range(0, len(ids), BATCH_SIZE):
                end = min(start + BATCH_SIZE, len(ids))
                tb = time.perf_counter()
                await ns_rw.write(
                    upsert_columns={"id": ids[start:end], "vector": vecs[start:end].tolist()},
                    distance_metric="cosine_distance",
                )
                ms = (time.perf_counter() - tb) * 1000
                written += end - start
                write_events.append({"wall_t": round(time.perf_counter()-t0,3), "vectors_written": written, "batch_ms": round(ms,1)})
            upload_end_t = time.perf_counter() - t0
            upload_done  = True
            print(f"  tpuf writer done at t={upload_end_t:.1f}s", flush=True)
        finally:
            stop_event.set()

    async def reader():
        await asyncio.sleep(1.0)
        q_idx = 0
        while not stop_event.is_set() or (upload_done and (time.perf_counter()-t0) <= upload_end_t + RW_POST_UPLOAD_S):
            tr = time.perf_counter()
            test = tests[q_idx % len(tests)]
            q_idx += 1
            try:
                r  = await ns_rw.query(rank_by=("vector","ANN",test["query"]), top_k=10, include_attributes=False)
                ms = (time.perf_counter() - tr) * 1000
                p  = r.performance
                liwa = None
                if p and p.last_included_write_at:
                    try:
                        raw = p.last_included_write_at
                        if isinstance(raw, str):
                            raw = raw.rstrip("Z").split(".")[0]
                            raw = datetime.datetime.fromisoformat(raw).replace(tzinfo=datetime.timezone.utc)
                        now_utc = datetime.datetime.now(datetime.timezone.utc)
                        liwa = round((now_utc - raw).total_seconds() * 1000, 1)
                    except Exception:
                        pass
                row: dict = {
                    "wall_t":                  round(time.perf_counter()-t0,3),
                    "total_ms":                round(ms,1),
                    "server_total_ms":         p.server_total_ms if p else None,
                    "exhaustive_search_count": p.exhaustive_search_count if p else None,
                    "staleness_ms":            liwa,
                    "n_results":               len(r.rows),
                }
                # recall only meaningful for non-MT datasets (MT uses a single mixed-tenant RW ns)
                if not ds.tenant_field and test.get("closest_ids"):
                    row["recall"] = round(recall_at_k([x.id for x in r.rows], test["closest_ids"]), 4)
                read_events.append(row)
            except Exception as e:
                read_events.append({"wall_t": round(time.perf_counter()-t0,3), "error": str(e)})
            if upload_done and (time.perf_counter()-t0) > upload_end_t + RW_POST_UPLOAD_S:
                break
            await asyncio.sleep(RW_READ_INTERVAL)

    await asyncio.gather(writer(), reader(), return_exceptions=True)
    return {"write_events": write_events, "read_events": read_events, "upload_end_t": upload_end_t}


async def _run_write_read_qdrant(ds: DatasetConfig, vecs, ids, tests, payloads, run_dir, state, args):
    """Concurrent write+read for Qdrant."""
    t0 = time.perf_counter()
    write_events:  list[dict] = []
    read_events:   list[dict] = []
    qdrant_info_events: list[dict] = []
    upload_done  = False
    upload_end_t = 0.0
    stop_event   = asyncio.Event()

    qc = make_qdrant()
    try:
        await qc.delete_collection(ds.qdrant_col_rw)
        print(f"  qdrant: cleared {ds.qdrant_col_rw}")
    except Exception:
        pass
    await qc.create_collection(
        collection_name=ds.qdrant_col_rw,
        vectors_config=models.VectorParams(size=ds.dims, distance=models.Distance.COSINE),
        hnsw_config=models.HnswConfigDiff(m=ds.hnsw_m, ef_construct=ds.hnsw_ef),
        optimizers_config=models.OptimizersConfigDiff(memmap_threshold=10_000_000),
    )

    async def writer():
        nonlocal upload_done, upload_end_t
        try:
            written = 0
            for start in range(0, len(ids), BATCH_SIZE):
                end = min(start + BATCH_SIZE, len(ids))
                points = [{"id": int(ids[start+i]), "vector": vecs[start+i].tolist(),
                           **({"payload": payloads[start+i]} if payloads else {})}
                          for i in range(end-start)]
                tb = time.perf_counter()
                await qdrant_upsert_timed(ds.qdrant_col_rw, points)
                batch_ms = (time.perf_counter() - tb) * 1000  # wall-clock, matches tpuf writer
                written += end - start
                write_events.append({"wall_t": round(time.perf_counter()-t0,3), "vectors_written": written, "batch_ms": round(batch_ms,1)})
            upload_end_t = time.perf_counter() - t0
            upload_done  = True
            print(f"  qdrant writer done at t={upload_end_t:.1f}s", flush=True)
        finally:
            stop_event.set()

    async def reader():
        await asyncio.sleep(1.0)
        q_idx = 0
        while not stop_event.is_set() or (upload_done and (time.perf_counter()-t0) <= upload_end_t + RW_POST_UPLOAD_S):
            tr   = time.perf_counter()
            test = tests[q_idx % len(tests)]
            q_idx += 1
            try:
                raw = await qc.http.search_api.query_points(
                    collection_name=ds.qdrant_col_rw,
                    query_request=models.QueryRequest(
                        query=test["query"],
                        filter=to_qdrant_filter(test.get("conditions") or {}) if ds.has_filter else None,
                        params=models.SearchParams(hnsw_ef=128),
                        limit=10, with_vector=False, with_payload=False,
                    ),
                )
                ms = (time.perf_counter() - tr) * 1000
                row: dict = {
                    "wall_t":    round(time.perf_counter()-t0,3),
                    "total_ms":  round(ms,1),
                    "server_ms": round(raw.time*1000,1),
                    "n_results": len(raw.result.points),
                }
                # recall only meaningful for non-MT datasets (MT uses a single mixed-tenant RW collection)
                if not ds.tenant_field and test.get("closest_ids"):
                    row["recall"] = round(recall_at_k([pt.id for pt in raw.result.points], test["closest_ids"]), 4)
                read_events.append(row)
            except Exception as e:
                read_events.append({"wall_t": round(time.perf_counter()-t0,3), "error": str(e)})
            if upload_done and (time.perf_counter()-t0) > upload_end_t + RW_POST_UPLOAD_S:
                break
            await asyncio.sleep(RW_READ_INTERVAL)

    async def poller():
        while not stop_event.is_set() or (upload_done and (time.perf_counter()-t0) <= upload_end_t + RW_POST_UPLOAD_S):
            try:
                info = await qc.get_collection(ds.qdrant_col_rw)
                qdrant_info_events.append({
                    "wall_t":                round(time.perf_counter()-t0,3),
                    "points_count":          info.points_count,
                    "indexed_vectors_count": info.indexed_vectors_count,
                    "segments_count":        info.segments_count,
                })
            except Exception:
                pass
            await asyncio.sleep(5.0)
            if upload_done and (time.perf_counter()-t0) > upload_end_t + RW_POST_UPLOAD_S:
                break

    await asyncio.gather(writer(), reader(), poller(), return_exceptions=True)
    await qc.close()
    return {"write_events": write_events, "read_events": read_events,
            "qdrant_info_events": qdrant_info_events, "upload_end_t": upload_end_t}


async def op_write_read(ds: DatasetConfig, active: list[str], run_dir: Path, state: dict, args):
    print(f"\n═══ {ds.key}/write_read  variants={active} ═══")
    vecs  = np.load(ds.path / "vectors.npy")
    ids   = list(range(len(vecs)))
    tests = [json.loads(l) for l in open(ds.path / "tests.jsonl")]
    print(f"  {vecs.shape[0]} × {vecs.shape[1]}, {len(tests)} queries")

    payloads = None
    if ds.has_payload:
        payloads = [json.loads(l) for l in open(ds.path / "payloads.jsonl")]

    for variant in active:
        if is_variant_done(state, ds.key, "write_read", variant):
            print(f"  skip {variant} (done)")
            continue
        print(f"\n  ── {variant} ──")
        if variant == "tpuf":
            result = await _run_write_read_tpuf(ds, vecs, ids, tests, run_dir, state, args)
        else:
            result = await _run_write_read_qdrant(ds, vecs, ids, tests, payloads, run_dir, state, args)
        result["n_vectors"] = len(ids)
        result["n_queries"]  = len(tests)

        # Print summary
        r_evts = [e for e in result["read_events"] if "error" not in e]
        if r_evts:
            lats = [e["total_ms"] for e in r_evts]
            recs = [e["recall"] for e in r_evts if "recall" in e]
            print(f"  {variant}: upload_end={result['upload_end_t']:.1f}s  reads={len(r_evts)}"
                  f"  p50={np.percentile(lats,50):.1f}ms  p99={np.percentile(lats,99):.1f}ms"
                  + (f"  recall={np.mean(recs):.3f}" if recs else ""))
        mark_variant_done(run_dir, state, ds.key, "write_read", variant, result)


# ═══════════════════════════════════════════════════════════════════════════════
# OP: disk  (dbpedia only — paired upload+search, cold-valid)
# ═══════════════════════════════════════════════════════════════════════════════

async def op_disk(ds: DatasetConfig, active: list[str], run_dir: Path, state: dict, args):
    print(f"\n═══ {ds.key}/disk  variants={active} ═══")
    if ds.key != "dbpedia":
        print("  skip disk (dbpedia only)")
        return

    DISK_COLLECTIONS = {
        "qdrant_disk_vec": "reproduce-dbpedia-disk-vec",
        "qdrant_disk_all": "reproduce-dbpedia-disk-all",
    }

    vecs  = np.load(ds.path / "vectors.npy")
    ids   = list(range(len(vecs)))
    tests = [json.loads(l) for l in open(ds.path / "tests.jsonl")]
    print(f"  {vecs.shape[0]} × {vecs.shape[1]}, batch={BATCH_SIZE}")

    for variant in active:
        if is_variant_done(state, ds.key, "disk", variant):
            print(f"  skip {variant} (done)")
            continue
        coll = DISK_COLLECTIONS[variant]
        on_disk_index = (variant == "qdrant_disk_all")
        qc = make_qdrant()
        try:
            await qc.delete_collection(coll)
        except Exception:
            pass
        await qc.create_collection(
            collection_name=coll,
            vectors_config=models.VectorParams(size=ds.dims, distance=models.Distance.COSINE, on_disk=True),
            hnsw_config=models.HnswConfigDiff(m=ds.hnsw_m, ef_construct=ds.hnsw_ef, on_disk=on_disk_index),
            optimizers_config=models.OptimizersConfigDiff(memmap_threshold=10_000_000),
        )
        qt = await qdrant_upload(qc, coll, vecs, ids)
        print(f"  {variant} upload: {qt['total_s']/60:.1f}min  wps={qt['wps']}")

        # Cold search — valid immediately after upload before any warmup
        print(f"  cold-start: {N_COLD_DISK} queries p=1 ...")
        cold_results = {}
        for ef in EF_SWEEP_DISK:
            qfn = _make_qdrant_qfn(qc, coll, ds, hnsw_ef=ef)
            s   = await run_search(qfn, tests[:N_COLD_DISK], concurrency=1, n=N_COLD_DISK)
            cold_results[f"ef{ef}_p1_cold"] = s
            pstats(f"COLD {variant} ef={ef} p=1", s, f"recall={s.get('recall_pct','?')}%")

        # Warm search — independent warmup per ef/p combination
        warm_results = {}
        for p in [1, 8]:
            for ef in EF_SWEEP_DISK:
                qfn = _make_qdrant_qfn(qc, coll, ds, hnsw_ef=ef)
                await run_search(qfn, tests[:N_WARMUP], concurrency=p)
                s   = await run_search(qfn, tests, concurrency=p)
                warm_results[f"ef{ef}_p{p}_warm"] = s
                pstats(f"WARM {variant} ef={ef} p={p}", s, f"recall={s.get('recall_pct','?')}%")

        await qc.close()
        mark_variant_done(run_dir, state, ds.key, "disk", variant,
                         {"upload": qt, **cold_results, **warm_results})


# ═══════════════════════════════════════════════════════════════════════════════
# OP: delete  (scoped to selected datasets)
# ═══════════════════════════════════════════════════════════════════════════════

def _engine_filter_matches(args_engines, family: str) -> bool:
    """True if the engine family ('tpuf' or 'qdrant') passes the --engine prefix filter."""
    if not args_engines:
        return True
    return any(family.startswith(e) or e.startswith(family) for e in args_engines)


async def phase_delete(run_dir: Path, state: dict, args):
    datasets_to_clean = args.dataset if args.dataset else list(DATASETS.keys())
    print(f"\n═══ delete  datasets={datasets_to_clean} ═══")

    tc = make_tpuf()
    qc = make_qdrant()

    for ds_key in datasets_to_clean:
        ds = DATASETS[ds_key]

        if _engine_filter_matches(args.engine, "tpuf"):
            tpuf_names = [ds.tpuf_ns_pinned, ds.tpuf_ns_rw] if ds.tpuf_ns_pinned else [ds.tpuf_ns_rw]
            if ds.tenant_field:
                # List and delete all MT namespaces; deduplicate in case tpuf_ns_rw starts with tpuf_ns prefix
                try:
                    async for ns in tc.namespaces():
                        if ns.id.startswith(ds.tpuf_ns) and ns.id not in tpuf_names:
                            tpuf_names.append(ns.id)
                except Exception:
                    pass
            else:
                tpuf_names = [ds.tpuf_ns, ds.tpuf_ns_pinned, ds.tpuf_ns_rw, f"{ds.tpuf_ns}-cold"]

            for name in tpuf_names:
                if not name:
                    continue
                try:
                    await tc.namespace(name).delete_all()
                    print(f"  tpuf ✓ {name}")
                except Exception as e:
                    print(f"  tpuf skip {name}: {e}")

        if _engine_filter_matches(args.engine, "qdrant"):
            qdrant_names = [ds.qdrant_col, ds.qdrant_col_rw]
            if ds.qdrant_col_deferred:
                qdrant_names.append(ds.qdrant_col_deferred)
            if ds.key == "dbpedia":
                qdrant_names += ["reproduce-dbpedia-disk-vec", "reproduce-dbpedia-disk-all"]
            for name in qdrant_names:
                if not name:
                    continue
                try:
                    await qc.delete_collection(name)
                    print(f"  qdrant ✓ {name}")
                except Exception as e:
                    print(f"  qdrant skip {name}: {e}")

    await qc.close()
    mark_variant_done(run_dir, state, "delete", "delete", "all", {})


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

OP_FNS = {
    "upload":      op_upload,
    "search":      op_search,
    "sweep":       op_sweep,
    "search_cold": op_search_cold,
    "fixed_qps":   op_fixed_qps,
    "write_read":  op_write_read,
    "disk":        op_disk,
}

# "delete" is a special op not in MATRIX; must be explicitly requested.
ALL_OPS = ["delete"] + list(OP_FNS.keys())


async def main():
    valid_datasets = list(DATASETS.keys())

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", nargs="+", choices=valid_datasets, metavar="DATASET",
                    help=f"Run only these datasets. Choices: {', '.join(valid_datasets)}")
    ap.add_argument("--op",      nargs="+", choices=ALL_OPS, metavar="OP",
                    help=f"Run only these operations. Choices: {', '.join(ALL_OPS)}")
    ap.add_argument("--engine",  nargs="+", metavar="ENGINE",
                    help="Prefix filter for engine variants (e.g. 'tpuf' matches tpuf/tpuf_pinned_*; "
                         "'qdrant' matches qdrant/qdrant_deferred/qdrant_disk_*)")
    ap.add_argument("--pinned",  action="store_true",
                    help="Enable tpuf_pinned_* variants (off by default)")
    ap.add_argument("--skip",    nargs="+", metavar="PHASE", default=[],
                    help="Skip specific 'dataset/op' phases (e.g. mt/fixed_qps)")
    ap.add_argument("--resume",  metavar="DIR",
                    help="Resume from existing run directory")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print execution plan and exit without running anything")
    args = ap.parse_args()

    # Build to_run from PHASES filtered by --dataset / --op.
    # "delete" is excluded from the default run — it must be requested explicitly via --op delete.
    to_run = []
    for phase in PHASES:
        if phase == "delete":
            if args.op and "delete" in args.op:
                to_run.append(phase)
            continue
        ds_key, op = phase.split("/", 1)
        if args.dataset and ds_key not in args.dataset:
            continue
        if args.op and op not in args.op:
            continue
        to_run.append(phase)

    run_dir = Path(args.resume) if args.resume else Path(f"results/reproduce-{time.strftime('%Y-%m-%dT%H-%M-%S')}")
    run_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(run_dir)

    if args.dry_run:
        print(f"Run dir: {run_dir}\n")
        print("Execution plan:")
        for phase in to_run:
            if phase in args.skip:
                print(f"  SKIP  {phase}")
                continue
            if phase == "delete":
                print(f"  RUN   delete")
                continue
            ds_key, op = phase.split("/", 1)
            active = _active_variants(ds_key, op, args)
            if not active:
                print(f"  SKIP  {phase}  (no active variants)")
                continue
            done = [v for v in active if is_variant_done(state, ds_key, op, v)]
            pending = [v for v in active if not is_variant_done(state, ds_key, op, v)]
            status = "DONE" if not pending else ("PART" if done else "RUN ")
            print(f"  {status}  {phase:35s}  pending={pending}  done={done}")
        return

    print(f"Run dir: {run_dir}")
    print(f"Phases:  {to_run}")
    print(f"Pinned:  {args.pinned}")

    for phase in to_run:
        if phase in args.skip:
            print(f"\n  skip {phase} (--skip)")
            continue

        if phase == "delete":
            await phase_delete(run_dir, state, args)
            continue

        ds_key, op = phase.split("/", 1)
        ds = DATASETS[ds_key]
        active = _active_variants(ds_key, op, args)

        if not active:
            print(f"\n  skip {ds_key}/{op} (no active variants — need --pinned?)")
            continue

        if all_variants_done(state, ds_key, op, active):
            print(f"\n  skip {ds_key}/{op} (all variants done)")
            continue

        await OP_FNS[op](ds, active, run_dir, state, args)

    print(f"\n═══ All done → {run_dir}/state.json ═══")


if __name__ == "__main__":
    asyncio.run(main())
