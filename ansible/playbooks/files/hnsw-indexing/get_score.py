import json
import os.path

SERVER_NAME = os.getenv("SERVER_NAME", "qdrant")
SERVER_NAME_2 = os.getenv("SERVER_NAME_2", "qdrant")
SERVER_VERSION = os.getenv("SERVER_VERSION", "dev")
SERVER_VERSION_2 = os.getenv("SERVER_VERSION_2", "master")
BENCH = os.getenv("BENCH", "update")
DATA_DIR = os.getenv("DATA_DIR", "data")

filepaths = {
    f"{SERVER_NAME}-{SERVER_VERSION}": os.path.join(
        DATA_DIR, f"output-{SERVER_NAME}-{SERVER_VERSION}-{BENCH}.json"
    ),
    f"{SERVER_NAME_2}-{SERVER_VERSION_2}": os.path.join(
        DATA_DIR, f"output-{SERVER_NAME_2}-{SERVER_VERSION_2}-{BENCH}.json"
    ),
}


def main():
    results = {}

    for label, path in filepaths.items():
        with open(path, "r") as file:
            text = file.read()
            given_output = json.loads(text)

        precision_before_iteration = given_output.get("precision_before_iteration", 0.0)
        precision_after_iteration = given_output.get("precision_after_iteration", 1.0)
        score = round(precision_before_iteration / precision_after_iteration, 4)
        indexing_time = given_output.get("indexing_total_time_s", 0.0)
        results[label] = {
            "indexing_time": indexing_time,
            "precision_before_iteration": precision_before_iteration,
            "precision_after_iteration": precision_after_iteration,
            "precision_score": score,
        }

    result = ""
    for label, data in results.items():
        for key, value in data.items():
            result += f"{label}_{key}={value},"
    print(result)
    return result


if __name__ == "__main__":
    main()
