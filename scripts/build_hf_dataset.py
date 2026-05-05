#!/usr/bin/env python3
"""Build an AnnCompoundReader-format dataset from a HuggingFace dataset and upload to GCS."""
import argparse
import json
import tarfile
from pathlib import Path

import faiss
import numpy as np
from datasets import load_dataset
from google.cloud import storage


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--hf-dataset", required=True)
    p.add_argument("--output-name", required=True)
    p.add_argument("--vector-column", default="embedding")
    p.add_argument("--gcs-uri", required=True, help="e.g. gs://bucket/prefix/")
    p.add_argument("--split", default="train")
    p.add_argument("--num-queries", type=int, default=1000)
    p.add_argument("--top-k", type=int, default=100)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    print(f"Loading {args.hf_dataset} (split={args.split})...")
    ds = (
        load_dataset(args.hf_dataset, split=args.split)
        .select_columns([args.vector_column])
        .with_format("numpy")
    )

    print(f"Extracting column '{args.vector_column}' from {len(ds)} rows...")
    vectors = np.asarray(ds[:][args.vector_column], dtype=np.float32)
    n, d = vectors.shape
    print(f"Loaded {n} vectors of dimension {d}")

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vectors /= norms

    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(n)
    test = vectors[perm[: args.num_queries]]
    train = np.ascontiguousarray(vectors[perm[args.num_queries :]])
    del vectors
    print(f"Train: {train.shape}, Test: {test.shape}")

    print(f"Computing top-{args.top_k} neighbors with FAISS IndexFlatIP...")
    index = faiss.IndexFlatIP(d)
    index.add(train)
    scores, ids = index.search(test, args.top_k)

    out_dir = Path("/tmp") / args.output_name
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "vectors.npy", train)
    with open(out_dir / "tests.jsonl", "w") as f:
        for q, qids, qscores in zip(test, ids, scores):
            f.write(
                json.dumps(
                    {
                        "query": q.tolist(),
                        "conditions": {},
                        "closest_ids": qids.tolist(),
                        "closest_scores": qscores.tolist(),
                    }
                )
                + "\n"
            )
    print(f"Wrote {out_dir}/vectors.npy ({train.nbytes / 1e9:.2f} GB) and tests.jsonl")

    tar_path = Path("/tmp") / f"{args.output_name}.tgz"
    print(f"Creating {tar_path}...")
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(out_dir / "vectors.npy", arcname="vectors.npy")
        tar.add(out_dir / "tests.jsonl", arcname="tests.jsonl")

    if not args.gcs_uri.startswith("gs://"):
        raise ValueError("--gcs-uri must start with gs://")
    bucket_name, _, prefix = args.gcs_uri[len("gs://") :].partition("/")
    blob_name = f"{prefix.rstrip('/')}/{args.output_name}.tgz".lstrip("/")
    print(f"Uploading to gs://{bucket_name}/{blob_name}...")
    storage.Client().bucket(bucket_name).blob(blob_name).upload_from_filename(
        str(tar_path)
    )
    print("Done.")


if __name__ == "__main__":
    main()