import os
import shutil
import tarfile
import urllib.request
from dataclasses import dataclass
from typing import Optional

from benchmark import DATASETS_DIR
from dataset_reader.ann_h5_reader import AnnH5Reader
from dataset_reader.base_reader import BaseReader
from dataset_reader.json_reader import JSONReader
from dataset_reader.tar_compound_reader import TarCompoundReader


@dataclass
class DatasetConfig:
    vector_size: int
    distance: str
    name: str
    type: str
    path: str
    link: Optional[str] = None


READER_TYPE = {"h5": AnnH5Reader, "jsonl": JSONReader, "tar": TarCompoundReader}


class Dataset:
    def __init__(self, config: dict):
        self.config = DatasetConfig(**config)

    def download(self):
        target_path = DATASETS_DIR / self.config.path

        if target_path.exists():
            print(f"{target_path} already exists")
            return

        if self.config.link:
            print(f"Downloading {self.config.link}...")
            tmp_path, _ = urllib.request.urlretrieve(self.config.link)

            if tmp_path.endswith(".tgz") or tmp_path.endswith(".tar.gz"):
                print(f"Extracting: {tmp_path} -> {target_path}")
                (DATASETS_DIR / self.config.path).mkdir(exist_ok=True)
                file = tarfile.open(tmp_path)
                file.extractall(target_path)
                file.close()
                os.remove(tmp_path)
            else:
                print(f"Moving: {tmp_path} -> {target_path}")
                (DATASETS_DIR / self.config.path).parent.mkdir(exist_ok=True)
                shutil.copy2(tmp_path, target_path)
                os.remove(tmp_path)

    def get_reader(self, normalize: bool) -> BaseReader:
        reader_class = READER_TYPE[self.config.type]
        return reader_class(DATASETS_DIR / self.config.path, normalize=normalize)


if __name__ == "__main__":
    dataset = Dataset(
        {
            "name": "glove-25-angular",
            "vector_size": 25,
            "distance": "Cosine",
            "type": "h5",
            "path": "glove-25-angular/glove-25-angular.hdf5",
            "link": "http://ann-benchmarks.com/glove-25-angular.hdf5",
        }
    )

    dataset.download()
