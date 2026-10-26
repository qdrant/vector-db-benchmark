#!/usr/bin/env python3
"""Flatten overnight result JSON into the team report viewer.

Writes docs/visual/data.js (window.REPORT_DATA) and docs/visual/data.json.
FineWeb rows are kept but marked precision_scored=false so the slider
cannot treat dummy 1.0 as real recall.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CORE_DATASETS = (
    "glove-100-angular",
    "gist-960-euclidean",
    "dbpedia-openai-1M-1536-angular",
    "cohere-wiki-1m",
)
DATASET_LABELS = {
    "glove-100-angular": "glove-100",
    "gist-960-euclidean": "gist-960",
    "dbpedia-openai-1M-1536-angular": "dbpedia-1M",
    "cohere-wiki-1m": "cohere-1M",
    "fineweb-10b-dense-1m": "FineWeb-1M",
}
ENGINE_ORDER = (
    "qdrant",
    "weaviate",
    "milvus",
    "elasticsearch",
    "opensearch",
    "redis",
    "pgvector",
)
SEARCH_EF_KEYS = (
    "hnsw_ef",
    "ef",
    "EF",
    "num_candidates",
    "knn.algo_param.ef_search",
    "ef_search",
)
SKIP_NAME_PARTS = ("random-100",)


def search_ef(config: dict | None) -> int | None:
    if not config:
        return None
    for key in SEARCH_EF_KEYS:
        if key in config and config[key] is not None:
            return int(config[key])
    for value in config.values():
        if isinstance(value, dict):
            found = search_ef(value)
            if found is not None:
                return found
    return None


def parse_experiment(name: str) -> tuple[str, int, int] | None:
    if "-m-" not in name or "-ef-" not in name:
        return None
    engine, rest = name.split("-m-", 1)
    try:
        m_str, efc_str = rest.split("-ef-")
        return engine, int(m_str), int(efc_str)
    except ValueError:
        return None


def _is_skipped(path: Path) -> bool:
    name = path.name
    return any(part in name for part in SKIP_NAME_PARTS)


def _latest_by_key(paths: list[Path], key_fn):
    latest = {}
    for path in paths:
        if _is_skipped(path):
            continue
        key = key_fn(path)
        if key is None:
            continue
        prev = latest.get(key)
        if prev is None or path.stat().st_mtime > prev.stat().st_mtime:
            latest[key] = path
    return latest


def _dataset_from_name(name: str, experiment: str) -> str | None:
    prefix = f"{experiment}-"
    for suffix in ("-search-", "-upload-"):
        if suffix in name and name.startswith(prefix):
            mid = name[len(prefix) :]
            cut = mid.find(suffix)
            if cut > 0:
                return mid[:cut]
    return None


def load_report(results_dir: Path) -> dict:
    search_files = _latest_by_key(
        list(results_dir.glob("*-search-*.json")),
        lambda p: (p.name.rsplit("-search-", 1)[0], p.name.split("-search-", 1)[1].split("-")[0]),
    )
    upload_files = _latest_by_key(
        list(results_dir.glob("*-upload-*.json")),
        lambda p: p.name.rsplit("-upload-", 1)[0],
    )

    uploads = {}
    for path in upload_files.values():
        payload = json.loads(path.read_text())
        params = payload.get("params") or {}
        results = payload.get("results") or {}
        experiment = params.get("experiment") or ""
        parsed = parse_experiment(experiment)
        if parsed is None:
            continue
        engine, m, efc = parsed
        dataset = params.get("dataset") or _dataset_from_name(path.name, experiment)
        if not dataset:
            continue
        uploads[(engine, dataset, m, efc)] = {
            "upload_s": results.get("upload_time"),
            "index_s": results.get("total_time"),
        }

    cells = []
    coverage = defaultdict(lambda: defaultdict(lambda: {"uploads": 0, "searches": 0}))
    for (engine_ds, _sid), path in search_files.items():
        payload = json.loads(path.read_text())
        params = payload.get("params") or {}
        results = payload.get("results") or {}
        experiment = params.get("experiment") or ""
        parsed = parse_experiment(experiment)
        if parsed is None:
            continue
        engine, m, efc = parsed
        dataset = params.get("dataset") or _dataset_from_name(path.name, experiment)
        if not dataset:
            continue
        ef = search_ef(params.get("config"))
        if ef is None:
            continue
        upload = uploads.get((engine, dataset, m, efc), {})
        scored = dataset in CORE_DATASETS
        precision = results.get("mean_precisions")
        if not scored:
            precision = None
        p95 = results.get("p95_time")
        mean = results.get("mean_time")
        cells.append(
            {
                "engine": engine,
                "dataset": dataset,
                "dataset_label": DATASET_LABELS.get(dataset, dataset),
                "m": m,
                "ef_construct": efc,
                "search_ef": ef,
                "parallel": int(params.get("parallel") or 0),
                "precision": precision,
                "precision_scored": scored,
                "p95_ms": p95 * 1000.0 if p95 is not None else None,
                "mean_ms": mean * 1000.0 if mean is not None else None,
                "rps": results.get("rps"),
                "upload_s": upload.get("upload_s"),
                "index_s": upload.get("index_s"),
                "experiment": experiment,
                "appendix": dataset not in CORE_DATASETS,
            }
        )
        coverage[engine][dataset]["searches"] += 1

    for engine, dataset, m, efc in uploads:
        coverage[engine][dataset]["uploads"] += 1

    coverage_out = {
        engine: {
            dataset: dict(stats)
            for dataset, stats in sorted(datasets.items())
        }
        for engine, datasets in coverage.items()
    }

    core_cells = [c for c in cells if not c["appendix"]]
    engines_present = [e for e in ENGINE_ORDER if e in coverage_out]
    extra = [e for e in coverage_out if e not in ENGINE_ORDER]
    need = len(CORE_DATASETS) * 96
    leftover, missing = [], []
    for engine in ENGINE_ORDER:
        searches = sum(
            (coverage_out.get(engine, {}).get(dataset) or {}).get("searches", 0)
            for dataset in CORE_DATASETS
        )
        if searches == 0:
            missing.append(engine)
        elif searches < need:
            leftover.append(f"{engine} {searches}/{need}")
    note_bits = ["Internal preview. Not the customer website."]
    if leftover:
        note_bits.append("Still running: " + ", ".join(leftover) + ".")
    if missing:
        note_bits.append("Not started: " + ", ".join(missing) + ".")
    if not leftover and not missing:
        note_bits.append("Core grid complete.")
    note_bits.append("FineWeb is an appendix and is not in this ranking.")
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": "AWS c6id.metal, NUMA-pinned (engine 0-31 / client 32-63)",
        "deadline": "EOD Wednesday 28 Oct 2026, Pacific (PDT)",
        "note": " ".join(note_bits),
        "core_datasets": list(CORE_DATASETS),
        "dataset_labels": DATASET_LABELS,
        "engine_order": engines_present + extra,
        "coverage": coverage_out,
        "cells": cells,
        "n_search_cells": len(cells),
        "n_core_search_cells": len(core_cells),
    }


def write_report(report: dict, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "data.json"
    js_path = out_dir / "data.js"
    text = json.dumps(report, indent=2)
    json_path.write_text(text + "\n")
    js_path.write_text("window.REPORT_DATA = " + json.dumps(report) + ";\n")
    return json_path, js_path


def main() -> None:
    repo = Path(__file__).resolve().parent.parent
    default_results = Path(
        os.environ.get("BENCHMARK_RESULTS_DIR", "/mnt/benchmark/results")
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=default_results)
    parser.add_argument("--out", type=Path, default=repo / "docs" / "visual")
    args = parser.parse_args()
    report = load_report(args.results)
    json_path, js_path = write_report(report, args.out)
    print(
        f"wrote {json_path} and {js_path} "
        f"({report['n_core_search_cells']} core search cells, "
        f"{report['n_search_cells']} total)"
    )


if __name__ == "__main__":
    main()
