import fnmatch
import traceback
from typing import List

import stopit
import typer

from benchmark.config_read import read_engine_configs, read_snapshot_config
from benchmark.snapshot import Snapshot
from engine.base_client import IncompatibilityError
from engine.clients.client_factory import ClientFactory

app = typer.Typer()


@app.command()
def run(
    engines: List[str] = typer.Option(["*"]),
    snapshots: List[str] = typer.Option(["*"]),
    host: str = "localhost",
    exit_on_error: bool = True,
    timeout: float = 86400.0,
):
    """
    Example:
        python3 recover_snapshot.py --engines "qdrant-*" --snapshots "200k-*"
    """
    all_engines = read_engine_configs()
    all_snapshots = read_snapshot_config()

    selected_engines = {
        name: config
        for name, config in all_engines.items()
        if any(fnmatch.fnmatch(name, engine) for engine in engines)
    }
    selected_snapshots = {
        name: config
        for name, config in all_snapshots.items()
        if any(fnmatch.fnmatch(name, snapshot) for snapshot in snapshots)
    }

    for engine_name, engine_config in selected_engines.items():
        for snapshot_name, snapshot_config in selected_snapshots.items():
            print(f"Running experiment: {engine_name} - {snapshot_name}")
            client = ClientFactory(host).build_client(engine_config)
            try:

                snapshot = Snapshot(snapshot_config)
                snapshot.download()

                with stopit.ThreadingTimeout(timeout) as tt:
                    client.recover_snapshot(snapshot)
                client.delete_client()

                # If the timeout is reached, the server might be still in the
                # middle of some background processing, like creating the index.
                # Next experiment should not be launched. It's better to reset
                # the server state manually.
                if tt.state != stopit.ThreadingTimeout.EXECUTED:
                    print(
                        f"Timed out {engine_name} - {snapshot_name}, "
                        f"exceeded {timeout} seconds"
                    )
                    exit(2)
            except IncompatibilityError as e:
                print(
                    f"Skipping {engine_name} - {snapshot_name}, incompatible params:", e
                )
                continue
            except KeyboardInterrupt:
                traceback.print_exc()
                exit(1)
            except Exception as e:
                print(f"Experiment {engine_name} - {snapshot_name} interrupted")
                traceback.print_exc()
                if exit_on_error:
                    raise e
                continue


if __name__ == "__main__":
    app()
