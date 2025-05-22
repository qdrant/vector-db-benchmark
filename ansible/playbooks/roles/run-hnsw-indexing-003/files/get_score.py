import os.path
import re


SERVER_NAME = os.getenv("SERVER_NAME", "qdrant")
SERVER_NAME_2 = os.getenv("SERVER_NAME_2", "qdrant")
SERVER_VERSION = os.getenv("SERVER_VERSION", "dev")
SERVER_VERSION_2 = os.getenv("SERVER_VERSION_2", "master")
BENCH = os.getenv("BENCH", "003")
DATA_DIR = os.getenv("DATA_DIR", "data")

filepaths = {
    f"{SERVER_NAME}-{SERVER_VERSION}": os.path.join(DATA_DIR, f"output-{SERVER_NAME}-{SERVER_VERSION}-{BENCH}.txt"),
    f"{SERVER_NAME_2}-{SERVER_VERSION_2}": os.path.join(DATA_DIR, f"output-{SERVER_NAME_2}-{SERVER_VERSION_2}-{BENCH}.txt")
}


def main():
    # Regular expressions to extract needed data
    initial_re = re.compile(r"Initial precision dataset1:\s+([\d.]+)")
    final_re = re.compile(r"Precision dataset2:\s+([\d.]+)")
    indexing_re = re.compile(r"Indexing: ([\d.]+)")

    results = {}

    # Parse file
    for label, path in filepaths.items():
        with open(path, "r") as file:
            text = file.read()

        initial = float(initial_re.search(text).group(1))
        final = float(final_re.search(text).group(1))
        indexing_time = float(indexing_re.search(text).group(1))

        score = round(initial / final, 4)
        results[label] = {
            "score": score,
            "indexing_time": indexing_time
        }

    result = ""
    for label, data in results.items():
        result += f"{label}_score={data['score']},{label}_indexing_time={data['indexing_time']},"
    print(result)
    return result


if __name__ == "__main__":
    main()
