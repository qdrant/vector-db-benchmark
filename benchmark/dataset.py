import os
import shutil
import tarfile
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional
from urllib.request import build_opener, install_opener

import tqdm

from benchmark import DATASETS_DIR
from dataset_reader.ann_compound_reader import AnnCompoundReader
from dataset_reader.ann_h5_reader import AnnH5Reader
from dataset_reader.base_reader import BaseReader
from dataset_reader.json_reader import JSONReader
from dataset_reader.sparse_reader import SparseReader

# Needed for Cloudflare's firewall in ann-benchmarks
# See https://github.com/erikbern/ann-benchmarks/pull/561
opener = build_opener()
opener.addheaders = [("User-agent", "Mozilla/5.0")]
install_opener(opener)


@dataclass
class DatasetConfig:
    name: str
    type: str
    path: str

    link: Optional[str] = None
    schema: Optional[Dict[str, str]] = field(default_factory=dict)
    # None in case of sparse vectors:
    vector_size: Optional[int] = None
    distance: Optional[str] = None


READER_TYPE = {
    "h5": AnnH5Reader,
    "jsonl": JSONReader,
    "tar": AnnCompoundReader,
    "sparse": SparseReader,
}


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
            with tqdm.tqdm(
                unit="B", unit_scale=True, miniters=1, dynamic_ncols=True, disable=None
            ) as t:
                tmp_path, _ = urllib.request.urlretrieve(
                    self.config.link, reporthook=_tqdm_reporthook(t)
                )

            if self.config.link.endswith(".tgz") or self.config.link.endswith(
                ".tar.gz"
            ):
                print(f"Extracting: {tmp_path} -> {target_path}")
                (DATASETS_DIR / self.config.path).mkdir(exist_ok=True, parents=True)
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


def _tqdm_reporthook(t: tqdm.tqdm) -> Callable[[int, int, int], None]:
    def reporthook(blocknum: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            t.total = total_size
        t.update(blocknum * block_size - t.n)

    return reporthook


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
