import json
import os.path
import tempfile
import urllib.request

import h5py

URL = "http://ann-benchmarks.com/glove-100-angular.hdf5"
KEYS = ["train", "test"]

if all(os.path.exists(f"/dataset/{key}.jsonl") for key in KEYS):
    exit()

with tempfile.NamedTemporaryFile() as tmpfile:
    urllib.request.urlretrieve(URL, tmpfile.name)
    dataset = h5py.File(tmpfile.name)

    for key in KEYS:
        with open(f"/dataset/{key}.jsonl", "w") as fp:
            fp.writelines(
                [json.dumps(vector.tolist()) + "\n" for vector in dataset[key]]
            )
