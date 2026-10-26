from tools.export_report_data import parse_experiment, search_ef


def test_search_ef_reads_engine_specific_keys():
    assert search_ef({"hnsw_ef": 100}) == 100
    assert search_ef({"ef": 200}) == 200
    assert search_ef({"EF": 500}) == 500
    assert search_ef({"num_candidates": 1000}) == 1000
    assert search_ef({"knn.algo_param.ef_search": 200}) == 200


def test_parse_experiment():
    assert parse_experiment("qdrant-m-16-ef-100") == ("qdrant", 16, 100)
    assert parse_experiment("elasticsearch-m-64-ef-1000") == (
        "elasticsearch",
        64,
        1000,
    )
    assert parse_experiment("not-a-cell") is None
