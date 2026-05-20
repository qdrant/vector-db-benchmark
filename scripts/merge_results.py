#!/usr/bin/env python3
"""Merge multiple benchmark result JSON files by averaging numeric metrics.

Usage:
    python scripts/merge_results.py results-run1.json results-run2.json results-run3.json -o merged-results.json

Records are matched by (setup_name, dataset_name, search_idx, parallel).
Numeric fields are averaged. Non-numeric fields (engine_params, engine_name) are taken from the first occurrence.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

NUMERIC_FIELDS = [
    "rps",
    "mean_time",
    "p95_time",
    "p99_time",
    "mean_precisions",
    "upload_time",
    "total_upload_time",
]

KEY_FIELDS = ("setup_name", "dataset_name", "search_idx", "parallel")


def record_key(record):
    return tuple(record.get(f) for f in KEY_FIELDS)


def average(values):
    return sum(values) / len(values)


def merge_recall_at_1_at_k(records):
    """Average recall_at_1_at_k dicts across records."""
    all_k = defaultdict(list)
    for r in records:
        rat = r.get("recall_at_1_at_k")
        if not rat:
            continue
        for k, v in rat.items():
            all_k[k].append(v)
    if not all_k:
        return None
    return {k: average(vs) for k, vs in sorted(all_k.items(), key=lambda x: int(x[0]))}


def merge(files):
    grouped = defaultdict(list)

    for path in files:
        data = json.loads(Path(path).read_text())
        for record in data:
            grouped[record_key(record)].append(record)

    merged = []
    for key, records in grouped.items():
        # Start from first record as base
        base = dict(records[0])
        n = len(records)

        # Average numeric fields
        for field in NUMERIC_FIELDS:
            values = [r[field] for r in records if field in r and r[field] is not None]
            if values:
                base[field] = average(values)

        # Average recall_at_1_at_k
        rat = merge_recall_at_1_at_k(records)
        if rat is not None:
            base["recall_at_1_at_k"] = rat

        base["_merged_from"] = n
        merged.append(base)

    return merged


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("files", nargs="+", help="Result JSON files to merge")
    parser.add_argument(
        "-o",
        "--output",
        default="merged-results.json",
        help="Output file (default: merged-results.json)",
    )
    args = parser.parse_args()

    for f in args.files:
        if not Path(f).exists():
            print(f"Error: {f} not found", file=sys.stderr)
            sys.exit(1)

    merged = merge(args.files)
    Path(args.output).write_text(json.dumps(merged, indent=2))

    # Summary
    counts = defaultdict(int)
    for r in merged:
        counts[r.get("_merged_from", 1)] += 1
    print(
        f"Merged {sum(len(json.loads(Path(f).read_text())) for f in args.files)} records from {len(args.files)} files into {len(merged)} entries"
    )
    for n, c in sorted(counts.items()):
        print(f"  {c} entries averaged from {n} run(s)")
    print(f"Written to {args.output}")


if __name__ == "__main__":
    main()
