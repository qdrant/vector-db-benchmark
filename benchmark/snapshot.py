import os
import shutil
import tarfile
import urllib.request
from dataclasses import dataclass
from typing import Optional

from benchmark import SNAPSHOTS_DIR


@dataclass
class SnapshotConfig:
    name: str
    path: str

    link: Optional[str] = None
    vector_size: Optional[int] = None


class Snapshot:
    def __init__(self, config: dict):
        self.config = SnapshotConfig(**config)

    def download(self):
        target_path = SNAPSHOTS_DIR / self.config.path

        if target_path.exists():
            print(f"{target_path} already exists")
            return

        if self.config.link:
            print(f"Downloading {self.config.link}...")
            tmp_path, _ = urllib.request.urlretrieve(self.config.link)

            if self.config.link.endswith(".tgz") or self.config.link.endswith(
                ".tar.gz"
            ):
                print(f"Extracting: {tmp_path} -> {target_path}")
                (SNAPSHOTS_DIR / self.config.path).mkdir(exist_ok=True, parents=True)
                file = tarfile.open(tmp_path)
                file.extractall(target_path)
                file.close()
                os.remove(tmp_path)
            else:
                print(f"Moving: {tmp_path} -> {target_path}")
                (SNAPSHOTS_DIR / self.config.path).parent.mkdir(exist_ok=True)
                shutil.copy2(tmp_path, target_path)
                os.remove(tmp_path)


if __name__ == "__main__":
    snapshot = Snapshot(
        {
            "name": "200k-768-disable-defrag",
            "vector_size": 768,
            "path": "200k-768-disable-defrag/middle-tenants-10-768-disable-defrag.snapshot",
            "link": "https://storage.googleapis.com/qdrant-benchmark-snapshots/on-disk-payload-index/middle-tenants-10-768-disable-defrag.snapshot",
        }
    )

    snapshot.download()
