import os
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Union

from dataset_reader.base_reader import BaseReader, Query, Record, SparseVector
from dataset_reader.fineweb_ids import fineweb_id_to_int, url_domain

FINEWEB_DIR_ENV = "FINEWEB_10B_DIR"
FINEWEB_QUERY_DIR_ENV = "FINEWEB_QUERY_DIR"
FINEWEB_MAX_VECTORS_ENV = "FINEWEB_MAX_VECTORS"
FINEWEB_QUERY_VECTORS_ENV = "FINEWEB_QUERY_VECTORS"
FINEWEB_SKIP_GT_ENV = "FINEWEB_SKIP_GT"
FINEWEB_USE_OFFICIAL_GT_ENV = "FINEWEB_USE_OFFICIAL_GT"

CORPUS_COLUMNS = (
    "id",
    "text",
    "url",
    "dump",
    "date",
    "language",
    "language_score",
    "token_count",
    "dense_embedding",
    "sparse_embedding",
)
QUERY_VECTOR_NAMES = (
    "bf_k1000_parsed_ids.parquet",
    "gt_dense_k1000.parquet",
    "dense_regenerated.parquet",
    "query_embeddings.parquet",
    "queries.parquet",
)


def _numbered_shard_dirs(root: Path) -> List[Path]:
    if not root.is_dir():
        return []
    # Count local overlay prefixes even when the S3 target is briefly
    # unreadable (expired token): is_dir() follows the symlink.
    dirs = [
        path
        for path in root.iterdir()
        if path.name.isdigit() and (path.is_symlink() or path.is_dir())
    ]
    return sorted(dirs, key=lambda path: path.name)


def _parquet_num_rows(path: Path) -> Optional[int]:
    try:
        import pyarrow.parquet as pq

        return pq.ParquetFile(path).metadata.num_rows
    except Exception:
        return None


def resolve_fineweb_root(path: Union[str, Path]) -> Path:
    env = os.environ.get(FINEWEB_DIR_ENV)
    if env:
        return Path(env).expanduser().resolve()
    configured = Path(path)
    if configured.is_absolute():
        return configured
    return configured


def fineweb_present(root: Path) -> bool:
    if not root.exists():
        return False
    if root.is_file():
        return root.suffix == ".parquet"
    if _numbered_shard_dirs(root) or _numbered_shard_dirs(root / "data"):
        return True
    return any(root.glob("*.parquet")) or any((root / "data").glob("*.parquet"))


class FineWebParquetReader(BaseReader):
    """Stream Qdrant/FineWeb-10B parquet from a local directory or single file.

    Expected layout (either is accepted):

    * a single ``*.parquet`` corpus file
    * a FineWeb-10B tree: ``data/**/*.parquet`` plus ``queries/gt_*.parquet``

    Query vectors are not redistributed. Place regenerated embeddings next to
    the GT files (``queries/regenerated/``) or set ``FINEWEB_QUERY_VECTORS``.

    Official top-1000 GT is for the full 10B UUID corpus. Slices therefore drop
    ``expected_result`` unless ``FINEWEB_USE_OFFICIAL_GT=1``.
    """

    def __init__(
        self,
        path: Union[str, Path],
        normalize: bool = False,
        query_file: Optional[str] = None,
        query_vectors: Optional[str] = None,
        max_vectors: Optional[int] = None,
        vector_kind: str = "dense",
        skip_ground_truth: bool = False,
        schema: Optional[dict] = None,
    ):
        self.path = resolve_fineweb_root(path)
        self.normalize = normalize
        self.query_file = query_file
        self.query_vectors = query_vectors
        self.max_vectors = _env_int(FINEWEB_MAX_VECTORS_ENV, max_vectors)
        self.vector_kind = vector_kind
        self.skip_ground_truth = skip_ground_truth or _env_flag(FINEWEB_SKIP_GT_ENV)
        self.schema = schema or {}

    @classmethod
    def from_config(
        cls, config, normalize: bool = False, path=None
    ) -> "FineWebParquetReader":
        return cls(
            path=path if path is not None else config.path,
            normalize=normalize,
            query_file=getattr(config, "query_file", None),
            query_vectors=getattr(config, "query_vectors", None),
            max_vectors=getattr(config, "max_vectors", None),
            vector_kind=getattr(config, "vector_kind", None) or "dense",
            skip_ground_truth=bool(getattr(config, "skip_ground_truth", False)),
            schema=getattr(config, "schema", None) or {},
        )

    def read_data(self) -> Iterator[Record]:
        import pyarrow.dataset as ds

        files = self._corpus_files()
        if not files:
            raise FileNotFoundError(self._missing_corpus_message())

        columns = self._corpus_columns(files[0])
        dataset = ds.dataset([str(path) for path in files], format="parquet")
        emitted = 0
        for batch in dataset.scanner(columns=columns, batch_size=1024).to_batches():
            for row in batch.to_pylist():
                yield self._record_from_row(row)
                emitted += 1
                if self.max_vectors is not None and emitted >= self.max_vectors:
                    return

    def read_queries(self) -> Iterator[Query]:
        import pyarrow.parquet as pq

        gt_path = self._ground_truth_path()
        if gt_path is None:
            raise FileNotFoundError(
                "FineWeb query/GT parquet not found. Place "
                f"{self.query_file or 'bf_k1000_parsed_ids.parquet'} under "
                f"{self._query_dir()} or set FINEWEB_QUERY_DIR / FINEWEB_10B_DIR."
            )

        table = pq.read_table(gt_path)
        rows = table.to_pylist()
        vectors = self._load_query_vectors(len(rows), rows)
        use_gt = self._should_use_ground_truth()
        if use_gt:
            print(
                "Using official FineWeb-10B ground truth; precision is only "
                "valid if the indexed corpus is the full 10B set."
            )

        for row, (dense, sparse) in zip(rows, vectors):
            yield Query(
                vector=self._maybe_normalize(dense),
                sparse_vector=sparse,
                meta_conditions=self._meta_conditions(row),
                expected_result=self._expected_ids(row) if use_gt else None,
                expected_scores=list(row["hit_scores"])
                if use_gt and row.get("hit_scores") is not None
                else None,
            )

    def _record_from_row(self, row: dict) -> Record:
        metadata = None
        if self.schema:
            metadata = {}
            for field in self.schema:
                if field == "domain":
                    metadata[field] = url_domain(row.get("url"))
                else:
                    metadata[field] = _as_python(row.get(field))
        return Record(
            id=fineweb_id_to_int(row["id"]),
            vector=self._maybe_normalize(_as_float_list(row.get("dense_embedding"))),
            sparse_vector=_as_sparse(row.get("sparse_embedding")),
            metadata=metadata,
        )

    def _maybe_normalize(self, vector: Optional[List[float]]) -> Optional[List[float]]:
        if vector is None or not self.normalize:
            return vector
        import numpy as np

        array = np.asarray(vector, dtype=np.float32)
        norm = np.linalg.norm(array)
        if norm == 0:
            return vector
        return (array / norm).tolist()

    def _corpus_files(self) -> List[Path]:
        root = self.path
        if root.is_file() and root.suffix == ".parquet":
            return [root]
        if not root.exists():
            return []
        data_dir = root / "data"
        search_root = data_dir if data_dir.is_dir() else root
        shard_dirs = _numbered_shard_dirs(search_root)
        if shard_dirs:
            return self._files_from_shard_dirs(shard_dirs)
        files = []
        for path in sorted(search_root.rglob("*.parquet")):
            if "queries" in path.parts:
                continue
            files.append(path)
            if self._enough_files(files):
                break
        return files

    def _files_from_shard_dirs(self, shard_dirs: List[Path]) -> List[Path]:
        files: List[Path] = []
        for directory in shard_dirs:
            for path in sorted(directory.glob("*.parquet")):
                files.append(path)
                if self._enough_files(files):
                    return files
        return files

    def _enough_files(self, files: List[Path]) -> bool:
        if self.max_vectors is None or not files:
            return False
        rows = _parquet_num_rows(files[0]) or 500_000
        return len(files) * rows >= self.max_vectors

    def _corpus_columns(self, sample: Path) -> List[str]:
        import pyarrow.parquet as pq

        available = set(pq.read_schema(sample).names)
        needed = ["id"]
        if self.vector_kind == "sparse":
            needed.append("sparse_embedding")
        else:
            needed.append("dense_embedding")
        for field in self.schema:
            source = "url" if field == "domain" else field
            if source in available:
                needed.append(source)
        return [name for name in CORPUS_COLUMNS if name in needed and name in available]

    def _query_dirs(self) -> List[Path]:
        dirs = []
        env = os.environ.get(FINEWEB_QUERY_DIR_ENV)
        if env:
            dirs.append(Path(env).expanduser())
        if self.path.is_file():
            sibling = self.path.parent / "queries"
            dirs.append(sibling if sibling.is_dir() else self.path.parent)
        else:
            dirs.append(self.path / "queries")
        home = os.environ.get("BENCHMARK_HOME")
        if home:
            dirs.append(Path(home) / "fineweb")
        dirs.append(Path("/mnt/benchmark/fineweb"))
        seen = set()
        unique = []
        for path in dirs:
            if path in seen:
                continue
            seen.add(path)
            unique.append(path)
        return unique

    def _query_dir(self) -> Path:
        for path in self._query_dirs():
            if path.is_dir():
                return path
        return self._query_dirs()[0]

    def _ground_truth_path(self) -> Optional[Path]:
        names = []
        if self.query_file:
            names.append(Path(self.query_file).name)
        if self.vector_kind == "sparse":
            names.append("gt_sparse_k1000.parquet")
        else:
            names.extend(
                ["bf_k1000_parsed_ids.parquet", "gt_dense_k1000.parquet"]
            )
        candidates = []
        if self.query_file:
            configured = Path(self.query_file)
            if configured.is_absolute():
                candidates.append(configured)
        for directory in self._query_dirs():
            for name in names:
                candidates.append(directory / name)
        for path in candidates:
            if path.is_file():
                return path
        return None

    def _load_query_vectors(
        self, n_queries: int, gt_rows: List[dict]
    ) -> List[tuple]:
        if gt_rows and self._row_has_query_vector(gt_rows[0]):
            return [self._vectors_from_row(row) for row in gt_rows]

        vector_path = self._query_vector_path()
        if vector_path is None:
            raise FileNotFoundError(
                "FineWeb query embeddings were not found. MS MARCO query text "
                "and vectors are not redistributed; regenerate them with the "
                "scripts under queries/scripts/ and place the parquet at "
                f"{self._query_dir() / 'regenerated'} or set {FINEWEB_QUERY_VECTORS_ENV}."
            )

        import pyarrow.parquet as pq

        rows = pq.read_table(vector_path).to_pylist()
        if len(rows) < n_queries:
            raise ValueError(
                f"Query vector file {vector_path} has {len(rows)} rows; "
                f"expected at least {n_queries}"
            )
        by_id = {}
        for row in rows:
            key = _query_key(row)
            if key is not None:
                by_id[key] = self._vectors_from_row(row)
        if by_id and _query_key(gt_rows[0]) in by_id:
            return [by_id[_query_key(row)] for row in gt_rows]
        return [self._vectors_from_row(row) for row in rows[:n_queries]]

    def _query_vector_path(self) -> Optional[Path]:
        env = os.environ.get(FINEWEB_QUERY_VECTORS_ENV)
        candidates = []
        if env:
            candidates.append(Path(env).expanduser())
        if self.query_vectors:
            configured = Path(self.query_vectors)
            candidates.append(
                configured
                if configured.is_absolute()
                else self._query_dir() / configured
            )
        for query_dir in self._query_dirs():
            regenerated = query_dir / "regenerated"
            if self.query_file:
                stem = Path(self.query_file).stem.replace("gt_", "").replace("_k1000", "")
                candidates.append(regenerated / f"{stem}_regenerated.parquet")
            for name in QUERY_VECTOR_NAMES:
                candidates.append(regenerated / name)
                candidates.append(query_dir / name)
        for path in candidates:
            if path.is_file():
                return path
        return None

    def _should_use_ground_truth(self) -> bool:
        if self.skip_ground_truth:
            return False
        if self.max_vectors is not None and not _env_flag(FINEWEB_USE_OFFICIAL_GT_ENV):
            return False
        return True

    def _expected_ids(self, row: dict) -> Optional[List[int]]:
        hits = (
            row.get("hit_fineweb_ids_cleaned")
            or row.get("hit_fineweb_ids")
            or row.get("hit_ids")
        )
        if hits is None:
            return None
        return [fineweb_id_to_int(hit) for hit in hits]

    def _meta_conditions(self, row: dict) -> Optional[dict]:
        conditions = []
        phrase = row.get("keyword_phrase")
        if phrase:
            conditions.append({"text": {"match_text": {"text": phrase}}})
        domains = _as_list(row.get("domains"))
        if domains:
            conditions.append({"domain": {"match_any": {"any": list(domains)}}})
        ls_gte = row.get("ls_gte")
        if ls_gte is not None:
            conditions.append({"language_score": {"range": {"gte": float(ls_gte)}}})
        date_gte, date_lt = row.get("date_gte"), row.get("date_lt")
        if date_gte is not None or date_lt is not None:
            bounds = {}
            if date_gte is not None:
                bounds["gte"] = str(date_gte)
            if date_lt is not None:
                bounds["lt"] = str(date_lt)
            conditions.append({"date": {"range": bounds}})
        dump_set = _as_list(row.get("dump_set"))
        if dump_set:
            conditions.append({"dump": {"match_any": {"any": list(dump_set)}}})
        if not conditions:
            return None
        return {"and": conditions}

    def _vectors_from_row(self, row: dict):
        dense = _as_float_list(
            row.get("dense_embedding") or row.get("query_dense_embedding")
        )
        sparse = _as_sparse(
            row.get("sparse_embedding") or row.get("query_sparse_embedding")
        )
        if self.vector_kind == "sparse":
            return None, sparse
        return dense, None

    @staticmethod
    def _row_has_query_vector(row: dict) -> bool:
        return any(
            row.get(name) is not None
            for name in (
                "dense_embedding",
                "sparse_embedding",
                "query_dense_embedding",
                "query_sparse_embedding",
            )
        )

    def _missing_corpus_message(self) -> str:
        return (
            f"FineWeb parquet not found at {self.path}. Place the original "
            "parquet file or the FineWeb-10B tree (data/**/*.parquet) there, "
            f"or set {FINEWEB_DIR_ENV} to that location. This reader does not "
            "download the 46.5 TB Hugging Face corpus."
        )


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def _env_int(name: str, default: Optional[int]) -> Optional[int]:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _as_python(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _as_float_list(value) -> Optional[List[float]]:
    if value is None:
        return None
    return [float(item) for item in value]


def _as_list(value) -> Optional[Sequence]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return value
    return [value]


def _as_sparse(value) -> Optional[SparseVector]:
    if value is None:
        return None
    if isinstance(value, SparseVector):
        return value
    if isinstance(value, dict):
        indices, values = value.get("indices"), value.get("values")
    else:
        try:
            indices, values = value[0], value[1]
        except (TypeError, IndexError, KeyError):
            return None
    if indices is None or values is None:
        return None
    return SparseVector(
        indices=[int(index) for index in indices],
        values=[float(item) for item in values],
    )


def _query_key(row: dict) -> Optional[tuple]:
    query_id = row.get("msmarco_query_id") or row.get("query_id")
    if query_id is None:
        return None
    return (
        row.get("msmarco_config"),
        row.get("msmarco_split"),
        str(query_id),
    )
