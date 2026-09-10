"""TCP client for the Infino build+serve process.

Infino builds and serves from a dedicated process (``python -m
infino._bench_serve --build``), so the benchmark client and the engine can run
on separate machines — the client here holds no embedded engine, only a socket.

One persistent connection drives the whole lifecycle over a little-endian,
opcode-tagged wire:

    CREATE   (u8 1, u32 dim, u32 metric_len, metric)          -> status
    APPEND   (u8 2, u32 nrows, u32 dim, nrows*(i64 id, dim*f32)) -> status, u64 count
    OPTIMIZE (u8 3)                                            -> status
    SEARCH   (u8 4, u32 k, u32 ef, u32 dim, dim*f32)           -> u32 n, n*i64 ids
    DROP     (u8 5)                                            -> status

``status`` is u8 0 on success, or u8 1 followed by u32 len + a UTF-8 message.
SEARCH returns dataset ids directly: the server maps the engine ``_id`` to the
stored dataset id from an in-memory table it builds at optimize, so the client
needs no id translation.
"""

import socket
import struct
from collections.abc import Sequence

import numpy as np

OP_CREATE = 1
OP_APPEND = 2
OP_OPTIMIZE = 3
OP_SEARCH = 4
OP_DROP = 5


def resolve_addr(host: str, connection_params: dict) -> tuple:
    """(host, port) from --host and connection_params (port env-defaulted)."""
    from engine.clients.infino.config import INFINO_PORT

    port = int(connection_params.get("port", INFINO_PORT))
    # --host may arrive as "host:port" or a URL; keep only the hostname.
    h = host
    if "://" in h:
        h = h.split("://", 1)[1]
    if "/" in h:
        h = h.split("/", 1)[0]
    if h.count(":") == 1:
        h, p = h.split(":")
        port = int(p)
    return h, port


class BuildConn:
    """One persistent socket to the build+serve process."""

    def __init__(self, host: str, port: int, timeout: float):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def _recv(self, n: int) -> bytes:
        buf = bytearray()
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("infino build-serve closed the connection")
            buf.extend(chunk)
        return bytes(buf)

    def _status(self) -> None:
        st = self._recv(1)[0]
        if st != 0:
            mlen = struct.unpack("<I", self._recv(4))[0]
            msg = self._recv(mlen).decode("utf-8", "replace")
            raise RuntimeError(f"infino build-serve error: {msg}")

    def create(self, dim: int, metric: str) -> None:
        mb = metric.encode()
        self.sock.sendall(struct.pack("<BII", OP_CREATE, dim, len(mb)) + mb)
        self._status()

    def append(self, ids: Sequence[int], vectors: np.ndarray) -> int:
        nrows = len(ids)
        if nrows == 0:
            return 0
        vecs = np.ascontiguousarray(vectors, dtype="<f4")
        if vecs.ndim != 2 or vecs.shape[0] != nrows:
            raise ValueError(
                f"expected {nrows} row vectors, got array of shape {vecs.shape}"
            )
        dim = vecs.shape[1]
        ids_arr = np.asarray(ids, dtype="<i8")
        # Pack each row as [i64 id][dim*f32], matching the server's row layout.
        row = np.empty((nrows, 8 + dim * 4), dtype=np.uint8)
        row[:, :8] = ids_arr.view(np.uint8).reshape(nrows, 8)
        row[:, 8:] = vecs.view(np.uint8).reshape(nrows, dim * 4)
        self.sock.sendall(struct.pack("<BII", OP_APPEND, nrows, dim) + row.tobytes())
        self._status()
        return struct.unpack("<Q", self._recv(8))[0]

    def optimize(self) -> None:
        self.sock.sendall(struct.pack("<B", OP_OPTIMIZE))
        self._status()

    def search(self, query: Sequence[float], k: int, ef: int = 0) -> list[int]:
        # ef is the hnsw serve-time beam for this query: 0 serves the graph's
        # stamped k->ef curve, a positive value walks at that fixed beam, so the
        # search sweep varies ef per point against one resident graph.
        q = np.ascontiguousarray(query, dtype="<f4")
        dim = q.shape[0]
        self.sock.sendall(struct.pack("<BIII", OP_SEARCH, k, ef, dim) + q.tobytes())
        n = struct.unpack("<I", self._recv(4))[0]
        if n == 0:
            return []
        if n > k:
            # The server returns at most k ids; a larger count means the wire is
            # out of sync — fail loudly rather than block on an oversized read.
            raise ConnectionError(f"infino build-serve returned {n} ids for k={k}")
        raw = self._recv(n * 8)
        return list(struct.unpack(f"<{n}q", raw))

    def drop(self) -> None:
        self.sock.sendall(struct.pack("<B", OP_DROP))
        self._status()

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass
