"""Small filesystem helpers shared across the tester."""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Atomically replace ``path`` with ``text``.

    Equivalent to ``open(..., newline="\\n")``: no newline translation happens,
    so ``\\n`` is written as-is on every platform. Readers observe either the
    previous file or the complete new file, never a partial write. The temporary
    file lives in the destination directory so ``os.replace`` stays on one
    filesystem.
    """

    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically replace ``path`` with ``data`` (temp file, fsync, ``os.replace``)."""

    destination = Path(path)
    # A uniquely named sibling opened with ``x`` keeps normal umask permissions,
    # unlike ``tempfile.mkstemp`` which always creates 0600 files.
    partial = destination.parent / f".{destination.name}.{uuid.uuid4().hex}.tmp"
    try:
        with partial.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(partial, destination)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
