from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO, Protocol

CHUNK_SIZE = 1024 * 1024


class _Digest(Protocol):
    def update(self, data: bytes, /) -> object: ...


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        _update_digest(stream, digest)
    return digest.hexdigest()


def copy_and_hash(
    source: Path, destination: Path, *, max_bytes: int | None = None
) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as reader, destination.open("xb") as writer:
        while chunk := reader.read(CHUNK_SIZE):
            size += len(chunk)
            if max_bytes is not None and size > max_bytes:
                raise ValueError(f"input exceeds {max_bytes} bytes")
            digest.update(chunk)
            writer.write(chunk)
    return digest.hexdigest(), size


def _update_digest(stream: BinaryIO, digest: _Digest) -> None:
    while chunk := stream.read(CHUNK_SIZE):
        digest.update(chunk)
