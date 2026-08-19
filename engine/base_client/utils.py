import functools
import io
import traceback
from multiprocessing.reduction import ForkingPickler
from typing import Callable, Iterable, List

from dataset_reader.base_reader import Record


def iter_batches(records: Iterable[Record], n: int) -> Iterable[List[Record]]:
    batch = []

    for record in records:
        batch.append(record)

        if len(batch) >= n:
            yield batch
            batch = []
    if len(batch) > 0:
        yield batch


class WorkerError(Exception):
    """Picklable stand-in for an exception raised inside a multiprocessing worker.

    Some client libraries raise exceptions that cannot be pickled (e.g. grpc
    errors hold a ``threading.RLock``). When such an exception escapes a pool
    worker, multiprocessing fails to send it back to the parent and reports an
    opaque ``MaybeEncodingError`` instead, hiding the actual failure. Re-raising
    the original traceback as this class keeps the diagnostics intact.
    """


def reraise_picklable(exc: BaseException) -> "WorkerError":
    """Wrap `exc` in a picklable error carrying its formatted traceback."""
    formatted = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    ).rstrip()
    return WorkerError(f"{type(exc).__module__}.{type(exc).__qualname__}\n{formatted}")


def picklable_errors(func: Callable) -> Callable:
    """Ensure exceptions raised by `func` can cross a multiprocessing boundary."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            try:
                ForkingPickler(io.BytesIO()).dump(exc)
            except Exception:
                raise reraise_picklable(exc) from None
            raise

    return wrapper
