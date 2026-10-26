import os
from pathlib import Path

# Base directory point to the main directory of the project, so all the data
# loaded from files can refer to it as a root directory

BASE_DIRECTORY = Path(__file__).parent.parent
CODE_DIR = os.path.dirname(__file__)
ROOT_DIR = Path(os.path.dirname(CODE_DIR))

_BENCHMARK_HOME = os.environ.get("BENCHMARK_HOME")
DATASETS_DIR = Path(
    os.environ.get(
        "BENCHMARK_DATASETS_DIR",
        Path(_BENCHMARK_HOME) / "datasets" if _BENCHMARK_HOME else BASE_DIRECTORY / "datasets",
    )
)
RESULTS_DIR = Path(
    os.environ.get(
        "BENCHMARK_RESULTS_DIR",
        Path(_BENCHMARK_HOME) / "results" if _BENCHMARK_HOME else ROOT_DIR / "results",
    )
)
