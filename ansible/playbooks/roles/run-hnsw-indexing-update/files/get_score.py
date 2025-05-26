import os.path
import re

SERVER_NAME = os.getenv("SERVER_NAME", "qdrant")
SERVER_NAME_2 = os.getenv("SERVER_NAME_2", "qdrant")
SERVER_VERSION = os.getenv("SERVER_VERSION", "dev")
SERVER_VERSION_2 = os.getenv("SERVER_VERSION_2", "master")
BENCH = os.getenv("BENCH", "update")
DATA_DIR = os.getenv("DATA_DIR", "data")

filepaths = {
    f"{SERVER_NAME}-{SERVER_VERSION}": os.path.join(
        DATA_DIR, f"output-{SERVER_NAME}-{SERVER_VERSION}-{BENCH}.txt"
    ),
    f"{SERVER_NAME_2}-{SERVER_VERSION_2}": os.path.join(
        DATA_DIR, f"output-{SERVER_NAME_2}-{SERVER_VERSION_2}-{BENCH}.txt"
    ),
}


def main():
    # Regular expressions to extract needed data
    after_del_re = re.compile(r"Precision after deletion:\s+([\d.]+)")
    iteration_re = re.compile(r"Iteration (\d+), Precision: ([\d.]+)")
    indexing_re = re.compile(r"Indexing: ([\d.]+)")

    results = {}

    for label, path in filepaths.items():
        with open(path, "r") as file:
            text = file.read()

        after_deletion = float(after_del_re.search(text).group(1))
        iterations = [
            (int(m.group(1)), float(m.group(2))) for m in iteration_re.finditer(text)
        ]
        indexing_time = float(indexing_re.search(text).group(1))

        score = round(after_deletion / iterations[-1][1], 4)
        results[label] = {"score": score, "indexing_time": indexing_time}

    result = ""
    for label, data in results.items():
        result += f"{label}_score={data['score']},{label}_indexing_time={data['indexing_time']},"
    print(result)
    return result


if __name__ == "__main__":
    main()
