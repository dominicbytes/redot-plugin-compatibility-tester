from __future__ import annotations

import hashlib
import os
import re
import time
import uuid
from pathlib import Path

from redot_compat.archive.hash import CHUNK_SIZE
from redot_compat.errors import SourceResolutionError

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
DEFAULT_MAX_BYTES = 10 * 1024**3


class ContentStore:
    """Content-addressed file store keyed by SHA-256, bounded by ``max_bytes``.

    Verification: ``get_file`` rehashes an object before returning it. Pass
    ``verify=False`` to skip hashing entirely (existence check only).

    Eviction: every hit and every insert stamps the object's access time
    explicitly, preserving mtime.
    After each ``put_file`` -- or on an explicit ``prune()`` -- the least recently
    used objects are deleted until the store fits within ``max_bytes``.
    Files larger than the bound are rejected rather than immediately evicted.
    """

    def __init__(self, root: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        if max_bytes < 0:
            raise ValueError("max_bytes must be non-negative")
        self.root = root.resolve()
        self.max_bytes = max_bytes
        self._objects.mkdir(parents=True, exist_ok=True)

    @property
    def _objects(self) -> Path:
        return self.root / "objects"

    def get_file(self, sha256: str, *, verify: bool = True) -> Path | None:
        path = self._object_path(sha256)
        try:
            stat = path.stat()
        except OSError:
            return None
        if not path.is_file():
            return None
        if verify and _sha256(path) != path.name:
            return None
        _touch_access(path, stat.st_mtime_ns)
        return path

    def put_file(self, source: Path, *, expected_sha256: str) -> Path:
        source_path = source.resolve(strict=True)
        if not source_path.is_file():
            raise SourceResolutionError("only regular files can enter the content store")
        if source_path.stat().st_size > self.max_bytes:
            raise SourceResolutionError("content-store input exceeds max_bytes")
        destination = self._object_path(expected_sha256)
        if valid := self.get_file(expected_sha256):
            self._evict(protect=valid)
            return valid
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.parent / f".{destination.name}.partial-{uuid.uuid4().hex}"
        digest = hashlib.sha256()
        try:
            with source_path.open("rb") as reader, partial.open("xb") as writer:
                while chunk := reader.read(CHUNK_SIZE):
                    digest.update(chunk)
                    writer.write(chunk)
                writer.flush()
                os.fsync(writer.fileno())
                if writer.tell() > self.max_bytes:
                    raise SourceResolutionError("content-store input exceeds max_bytes")
            if digest.hexdigest() != destination.name:
                raise SourceResolutionError("content-store input digest does not match its key")
            # os.replace atomically swaps any existing (e.g. corrupt) object.
            os.replace(partial, destination)
        finally:
            partial.unlink(missing_ok=True)
        stat = destination.stat()
        _touch_access(destination, stat.st_mtime_ns)
        self._evict(protect=destination)
        return destination

    def prune(self, *, max_bytes: int | None = None) -> list[Path]:
        """Evict least recently used objects until the store fits the bound.

        Returns the removed object paths. ``max_bytes`` overrides the store's
        configured bound for this call only.
        """

        return self._evict(protect=None, max_bytes=max_bytes)

    def total_bytes(self) -> int:
        return sum(size for _, size, _ in self._entries())

    def _evict(self, *, protect: Path | None, max_bytes: int | None = None) -> list[Path]:
        limit = self.max_bytes if max_bytes is None else max_bytes
        if limit < 0:
            raise ValueError("max_bytes must be non-negative")
        entries = self._entries()
        total = sum(size for _, size, _ in entries)
        removed: list[Path] = []
        for path, size, _ in sorted(entries, key=lambda entry: (entry[2], entry[0].name)):
            if total <= limit:
                break
            if protect is not None and path == protect:
                continue
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                continue
            total -= size
            removed.append(path)
        return removed

    def _entries(self) -> list[tuple[Path, int, int]]:
        """Committed objects as ``(path, size, last_used_ns)``; partials are skipped."""

        entries: list[tuple[Path, int, int]] = []
        for path in self._objects.glob("??/*"):
            if not _SHA256.fullmatch(path.name):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append((path, stat.st_size, max(stat.st_atime_ns, stat.st_mtime_ns)))
        return entries

    def _object_path(self, sha256: str) -> Path:
        normalized = sha256.casefold()
        if not _SHA256.fullmatch(normalized):
            raise ValueError("content key must be a lowercase SHA-256")
        return self._objects / normalized[:2] / normalized


def _touch_access(path: Path, mtime_ns: int) -> None:
    """Record a use for LRU eviction without changing mtime."""

    try:
        os.utime(path, ns=(max(time.time_ns(), mtime_ns), mtime_ns))
    except OSError:
        pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
