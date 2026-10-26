import uuid
from pathlib import Path

import pytest

from benchmark.dataset import Dataset
from dataset_reader.fineweb_ids import fineweb_id_to_int, url_domain
from dataset_reader.fineweb_reader import FineWebParquetReader
from engine.clients.qdrant.ids import qdrant_hit_id, qdrant_point_id

BARE_UUID = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
URN_ID = f"<urn:uuid:{BARE_UUID}>"


def test_fineweb_id_accepts_urn_and_bare_uuid():
    assert fineweb_id_to_int(URN_ID) == uuid.UUID(BARE_UUID).int
    assert fineweb_id_to_int(BARE_UUID) == uuid.UUID(BARE_UUID).int
    assert fineweb_id_to_int(uuid.UUID(BARE_UUID)) == uuid.UUID(BARE_UUID).int


def test_url_domain_extracts_host():
    assert url_domain("https://www.example.com/path") == "www.example.com"
    assert url_domain(None) is None


def test_qdrant_round_trips_uuid_ints():
    point_id = uuid.UUID(BARE_UUID).int
    stored = qdrant_point_id(point_id)
    assert stored == BARE_UUID
    assert qdrant_hit_id(stored) == point_id
    assert qdrant_point_id(7) == 7


def test_structured_and_text_filters_map_to_meta_conditions(tmp_path: Path):
    reader = FineWebParquetReader(tmp_path, schema={"text": "text", "domain": "keyword"})
    text_row = {
        "keyword_phrase": "climate change",
        "domains": ["example.com", "news.org"],
    }
    structured_row = {
        "ls_gte": 0.9,
        "date_gte": "2018-01-01T00:00:00Z",
        "date_lt": "2019-01-01T00:00:00Z",
        "dump_set": ["CC-MAIN-2018-17"],
    }
    assert reader._meta_conditions(text_row) == {
        "and": [
            {"text": {"match_text": {"text": "climate change"}}},
            {"domain": {"match_any": {"any": ["example.com", "news.org"]}}},
        ]
    }
    assert reader._meta_conditions(structured_row) == {
        "and": [
            {"language_score": {"range": {"gte": 0.9}}},
            {
                "date": {
                    "range": {
                        "gte": "2018-01-01T00:00:00Z",
                        "lt": "2019-01-01T00:00:00Z",
                    }
                }
            },
            {"dump": {"match_any": {"any": ["CC-MAIN-2018-17"]}}},
        ]
    }


def test_missing_corpus_raises(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("FINEWEB_10B_DIR", raising=False)
    reader = FineWebParquetReader(tmp_path / "missing.parquet")
    with pytest.raises(FileNotFoundError, match="FineWeb parquet not found"):
        next(reader.read_data())


def test_expected_ids_prefer_cleaned_uuids():
    reader = FineWebParquetReader("/tmp")
    row = {
        "hit_ids": ["ignored"],
        "hit_fineweb_ids": [URN_ID],
        "hit_fineweb_ids_cleaned": [BARE_UUID],
    }
    assert reader._expected_ids(row) == [uuid.UUID(BARE_UUID).int]


def test_reads_local_parquet_and_query_gt(tmp_path: Path, monkeypatch):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    monkeypatch.delenv("FINEWEB_10B_DIR", raising=False)
    monkeypatch.delenv("FINEWEB_QUERY_DIR", raising=False)
    monkeypatch.delenv("BENCHMARK_HOME", raising=False)
    monkeypatch.delenv("FINEWEB_MAX_VECTORS", raising=False)

    doc_id = f"<urn:uuid:{BARE_UUID}>"
    vector = [0.0] * 767 + [1.0]
    corpus = pa.table(
        {
            "id": [doc_id],
            "text": ["hello world"],
            "url": ["https://example.com/page"],
            "dump": ["CC-MAIN-2018-17"],
            "date": ["2018-06-01T00:00:00Z"],
            "language": ["en"],
            "language_score": [0.95],
            "token_count": [2],
            "dense_embedding": [vector],
            "sparse_embedding": [{"indices": [1, 4], "values": [0.2, 0.8]}],
        }
    )
    corpus_path = tmp_path / "shard.parquet"
    pq.write_table(corpus, corpus_path)

    queries_dir = tmp_path / "queries"
    queries_dir.mkdir()
    gt = pa.table(
        {
            "msmarco_config": ["v2.1"],
            "msmarco_split": ["test"],
            "msmarco_query_id": ["q1"],
            "hit_scores": [[1.0]],
            "hit_fineweb_ids": [[BARE_UUID]],
            "dense_embedding": [vector],
        }
    )
    pq.write_table(gt, queries_dir / "gt_dense_k1000.parquet")

    reader = FineWebParquetReader(
        corpus_path,
        schema={"text": "text", "domain": "keyword", "dump": "keyword"},
    )
    record = next(reader.read_data())
    assert record.id == uuid.UUID(BARE_UUID).int
    assert record.vector == vector
    assert record.metadata["domain"] == "example.com"
    assert record.metadata["dump"] == "CC-MAIN-2018-17"

    query = next(reader.read_queries())
    assert query.vector == vector
    assert query.expected_result == [uuid.UUID(BARE_UUID).int]


def test_slice_skips_official_ground_truth(tmp_path: Path):
    reader = FineWebParquetReader(tmp_path, max_vectors=1_000_000)
    assert reader._should_use_ground_truth() is False


def test_numbered_symlink_shards_count_as_present(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("FINEWEB_10B_DIR", raising=False)
    overlay = tmp_path / "overlay"
    target = tmp_path / "s3" / "00"
    target.mkdir(parents=True)
    overlay.mkdir()
    (overlay / "00").symlink_to(target)
    from dataset_reader.fineweb_reader import fineweb_present

    assert fineweb_present(overlay) is True


def test_finds_local_bf_query_parquet(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FINEWEB_QUERY_DIR", str(tmp_path))
    monkeypatch.delenv("FINEWEB_10B_DIR", raising=False)
    query_path = tmp_path / "bf_k1000_parsed_ids.parquet"
    query_path.write_bytes(b"parquet")
    reader = FineWebParquetReader(tmp_path / "corpus")
    assert reader._ground_truth_path() == query_path
    assert reader._query_vector_path() == query_path


def test_dataset_download_requires_local_parquet(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("FINEWEB_10B_DIR", raising=False)
    dataset = Dataset(
        {
            "name": "fineweb-10b-dense-1m",
            "vector_size": 768,
            "distance": "cosine",
            "type": "fineweb",
            "path": str(tmp_path / "absent"),
            "point_id": "uuid",
            "vector_kind": "dense",
            "max_vectors": 1000000,
            "skip_ground_truth": True,
        }
    )
    with pytest.raises(FileNotFoundError, match="FINEWEB_10B_DIR"):
        dataset.download()
