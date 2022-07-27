import os
from pathlib import Path

# Base directory point to the main directory of the project, so all the data
# loaded from files can refer to it as a root directory

BASE_DIRECTORY = Path(__file__).parent.parent
DATASETS_DIR = BASE_DIRECTORY / "datasets"
CODE_DIR = os.path.dirname(__file__)
ROOT_DIR = Path(os.path.dirname(CODE_DIR))
