import fnmatch
import traceback
from typing import List

import typer

from benchmark.config_read import read_snapshot_config
from benchmark.snapshot import Snapshot

app = typer.Typer()


@app.command()
def run(
    snapshots: List[str] = typer.Option(["*"]),
    exit_on_error: bool = True,
):
    """
    Example:
        python3 recover_snapshot.py --engines "qdrant-*" --snapshots "200k-*"
    """
    all_snapshots = read_snapshot_config()

    selected_snapshots = {
        name: config
        for name, config in all_snapshots.items()
        if any(fnmatch.fnmatch(name, snapshot) for snapshot in snapshots)
    }

    for snapshot_name, snapshot_config in selected_snapshots.items():
        print(f"Downloading snapshot: {snapshot_name}")
        try:

            snapshot = Snapshot(snapshot_config)
            snapshot.download()
        except KeyboardInterrupt:
            traceback.print_exc()
            exit(1)
        except Exception as e:
            print(f"Downloading {snapshot_name} interrupted")
            traceback.print_exc()
            if exit_on_error:
                raise e
            continue


if __name__ == "__main__":
    app()
