import json
import tempfile
import urllib.request
from pathlib import Path

import h5py

ROOT_DIR = Path(__file__).parent
URL = "http://ann-benchmarks.com/glove-100-angular.hdf5"


with tempfile.NamedTemporaryFile() as tmpfile:
    urllib.request.urlretrieve(URL, tmpfile.name)
    dataset = h5py.File(tmpfile.name)

    keys = ["train", "test"]
    for key in keys:
        with open(str(ROOT_DIR / f"{key}.jsonl"), "w") as fp:
            fp.writelines(
                [json.dumps(vector.tolist()) + "\n" for vector in dataset[key]]
            )
