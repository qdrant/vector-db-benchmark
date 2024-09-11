import argparse
import glob
import json
import os


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=str, required=True)
    parser.add_argument("--output-file", type=str, required=True)
    args = parser.parse_args()

    input_dir = args.input_dir
    output_file = args.output_file

    searches = glob.glob(os.path.join(input_dir, "*-search-*.json"))
    uploads = glob.glob(os.path.join(input_dir, "*-upload-*.json"))

    """
    Target data structure:

    {
      "engine_name": "qdrant",
      "setup_name": "qdrant-bq-rps-m-64-ef-256",
      "dataset_name": "dbpedia-openai-1M-1536-angular",
      "upload_time": 222.45490989403334,
      "total_upload_time": 593.0384756129934,
      "p95_time": 0.0025094749056734146,
      "rps": 1230.5984500596446,
      "parallel": 100.0,
      "p99_time": 0.014029250466264838,
      "mean_time": 0.00227582405093126,
      "mean_precisions": 0.95258,
      "engine_params": {
        "hnsw_ef": 64,
        "quantization": {
          "rescore": true,
          "oversampling": 4.0
        }
      }
    }
    """

    print(f"input_dir: {input_dir}")
    print(f"output_file: {output_file}")

    print(f"searches: {len(searches)}")
    print(f"uploads: {len(uploads)}")

    upload_data = {}

    for upload_file in uploads:
        data = json.load(open(upload_file))
        experiment_name = data["params"]["experiment"]
        upload_data[experiment_name] = data

    result_data = []

    for search_file in searches:
        data = json.load(open(search_file))
        experiment_name = data["params"]["experiment"]
        dataset_name = data["params"]["dataset"]
        engine_params = data["params"]["config"]
        parallel = data["params"]["parallel"]
        engine_name = data["params"]["engine"]

        upload_time = upload_data[experiment_name]["results"]["upload_time"]
        total_upload_time = upload_data[experiment_name]["results"]["total_time"]

        search_results = data["results"]
        search_results.pop("total_time")

        result_data.append(
            {
                "engine_name": engine_name,
                "setup_name": experiment_name,
                "dataset_name": dataset_name,
                "upload_time": upload_time,
                "total_upload_time": total_upload_time,
                "parallel": parallel,
                "engine_params": engine_params,
                **search_results,
            }
        )

    with open(output_file, "w") as f:
        json.dump(result_data, f, indent=2)


if __name__ == "__main__":
    main()
