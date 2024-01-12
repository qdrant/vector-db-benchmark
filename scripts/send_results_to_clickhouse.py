# sends the results to clickhouse where we can visualize
import os
from pathlib import Path
import re
import json
import pandas as pd

import clickhouse_connect
from clickhouse_connect.driver.models import ColumnDef

DATA_DIR = Path().resolve().parent / "results"
DATA_DIR, list(DATA_DIR.glob("*.json"))[0].name

PATH_REGEX = re.compile(r"(?P<engine_name>[a-z]+)-(?:.*?-?m-(?P<m>\d*)-ef-(?P<ef>\d*)-)?.*")

upload_results, search_results = [], []

for path in DATA_DIR.glob("*.json"):
    match = PATH_REGEX.match(path.name)
    if match is None:
        continue

    experiment = match.groupdict()

    with open(path, "r") as fp:
        stats = json.load(fp)

    entry = [stats["test_name"], match["engine_name"], 0 if match["m"] is None else int(match["m"]),
             0 if match["ef"] is None else int(match["ef"]),
             stats["dataset_name"], stats["search_id"] if "search_id" in stats else 0, stats["timestamp"],
             stats["params"], stats["results"]]
    if stats["operation"] == "search":
        search_results.append(entry)
    elif stats["operation"] == "upload":
        upload_results.append(entry)

column_names = ["test_name", "engine", "m", "ef", "dataset", "search_index", "date", "params", "results"]

upload_df = pd.DataFrame(upload_results, columns=column_names)
upload_df["date"] = pd.to_datetime(upload_df["date"], format="%Y-%m-%d-%H-%M-%S")

upload_df = upload_df.sort_values("date", ascending=False) \
    .groupby(["test_name", "dataset"]) \
    .last()
upload_df = pd.concat([upload_df, upload_df["results"].apply(pd.Series)], axis=1)
upload_df["total_upload_time"] = upload_df["total_time"]
upload_df = upload_df.drop(columns=["results", "latencies", "search_index", "engine", "ef", "m"])

search_df = pd.DataFrame(search_results, columns=column_names)
search_df["date"] = pd.to_datetime(search_df["date"], format="%Y-%m-%d-%H-%M-%S")
search_df = search_df.sort_values("date", ascending=False) \
    .groupby(["test_name", "dataset", "search_index"]) \
    .first()

summary_rows = {}

client = clickhouse_connect.get_client(host=os.getenv("CLICKHOUSE_HOST", "localhost"),
                                       username=os.getenv("CLICKHOUSE_USER", "default"),
                                       password=os.getenv("CLICKHOUSE_PASSWORD", ""),
                                       database=os.getenv("CLICKHOUSE_DATABASE", "default"),
                                       port=int(os.getenv("CLICKHOUSE_PORT", 8123)),
                                       secure=True if os.getenv("CLICKHOUSE_SECURE", "false").lower() == "true" else False)
client.command("DROP TABLE IF EXISTS vector_bench_summary")
client.command("CREATE TABLE IF NOT EXISTS vector_bench_summary ("
               "test_name LowCardinality(String),"
               "dataset LowCardinality(String), "
               "engine LowCardinality(String), "
               "m UInt16, "
               "ef UInt16, "
               "search_index UInt16,"
               "date_search DateTime, "
               "params_search Map(String, String),"
               "search_parallel UInt16, "
               "total_time Float64, "
               "mean_time Float64, "
               "mean_precisions Float64, "
               "std_time Float64, "
               "min_time Float64, "
               "max_time Float64,"
               "rps Float64,"
               "p95_time Float64,"
               "p99_time Float64, "
               "date_upload DateTime, "
               "upload_time Float64, "
               "total_upload_time Float64,"
               "index_parallel UInt16, "
               "batch_size UInt32,"
               "params_upload Map(String, String)) ENGINE = MergeTree ORDER BY (date_search, engine, dataset)")
data = []
_search = search_df.reset_index()
_upload = upload_df.reset_index()
joined_df = _search.merge(_upload, on=["test_name", "dataset"], how="left", suffixes=("_search", "_upload"))
for index, row in joined_df.reset_index().iterrows():
    data.append(
        [
            row["test_name"],
            row["dataset"],
            row["engine"],
            int(row["m"]),
            int(row["ef"]),
            int(row["search_index"]),
            row["date_search"],
            {key: str(value) for key, value in row['params_search'].items()},
            row['params_search']['parallel'],
            row['results']["total_time"],
            row['results']["mean_time"],
            row['results']["mean_precisions"],
            row['results']["std_time"],
            row['results']["min_time"],
            row['results']["max_time"],
            row['results']["rps"],
            row['results']["p95_time"],
            row['results']["p99_time"],
            row["date_upload"],
            row['upload_time'],
            row['total_upload_time'],
            int(row['parallel']),
            int(row['batch_size']),
            {key: str(value) for key, value in row['params_upload'].items()}
        ]
    )

describe_result = client.query(f'DESCRIBE TABLE vector_bench_summary')
column_defs = [ColumnDef(**row) for row in describe_result.named_results()
               if row['default_type'] not in ('ALIAS', 'MATERIALIZED')]
column_names = [cd.name for cd in column_defs]
column_types = [cd.ch_type for cd in column_defs]

client.insert("vector_bench_summary", data, column_names=column_names, column_types=column_types)
client.command("DROP TABLE IF EXISTS vector_bench_results")
client.command("CREATE TABLE IF NOT EXISTS vector_bench_results ("
               "test_name LowCardinality(String),"
               "dataset LowCardinality(String), "
               "engine LowCardinality(String), "
               "m UInt16, "
               "ef UInt16, "
               "search_index UInt16,"
               "date_search DateTime, "
               "params_search Map(String, String),"
               "search_parallel UInt16, "
               "date_upload DateTime, "
               "upload_time Float64, "
               "params_upload Map(String, String), "
               "latency Float64, "
               "total_upload_time Float64,"
               "index_parallel UInt16,"
               "batch_size UInt32,"
               "precision Float64, "
               "query_index UInt32) ENGINE = MergeTree ORDER BY (date_search, engine, dataset)")
data = []
for index, row in joined_df.reset_index().iterrows():
    for i, latency in enumerate(row["results"]["latencies"]):
        data.append(
            [
                row["test_name"],
                row["dataset"],
                row["engine"],
                int(row["m"]),
                int(row["ef"]),
                int(row["search_index"]),
                row["date_search"],
                {key: str(value) for key, value in row['params_search'].items()},
                row['params_search']['parallel'],
                row["date_upload"],
                row['upload_time'],
                {key: str(value) for key, value in row['params_upload'].items()},
                latency,
                row['total_upload_time'],
                int(row['parallel']),
                int(row['batch_size']),
                row["results"]["precisions"][i],
                i,
            ]
        )

describe_result = client.query(f'DESCRIBE TABLE vector_bench_results')
column_defs = [ColumnDef(**row) for row in describe_result.named_results()
               if row['default_type'] not in ('ALIAS', 'MATERIALIZED')]
column_names = [cd.name for cd in column_defs]
column_types = [cd.ch_type for cd in column_defs]
client.insert("vector_bench_results", data, column_names=column_names, column_types=column_types)