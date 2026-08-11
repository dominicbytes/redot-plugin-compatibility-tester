from __future__ import annotations

import hashlib
import os
import re
import uuid
from pathlib import Path

from redot_compat.archive.hash import CHUNK_SIZE
from redot_compat.errors import SourceResolutionError

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class ContentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        (self.root / "objects").mkdir(parents=True, exist_ok=True)

    def get_file(self, sha256: str) -> Path | None:
        path = self._object_path(sha256)
        if not path.is_file() or _sha256(path) != sha256:
            return None
        return path

    def put_file(self, source: Path, *, expected_sha256: str) -> Path:
        source_path = source.resolve(strict=True)
        if not source_path.is_file():
            raise SourceResolutionError("only regular files can enter the content store")
        destination = self._object_path(expected_sha256)
        if valid := self.get_file(expected_sha256):
            return valid
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.parent / f".{destination.name}.partial-{uuid.uuid4().hex}"
        digest = hashlib.sha256()
        try:
            with source_path.open("rb") as reader, partial.open("xb") as writer:
                while chunk := reader.read(CHUNK_SIZE):
                    digest.update(chunk)
                    writer.write(chunk)
            if digest.hexdigest() != expected_sha256:
                raise SourceResolutionError("content-store input digest does not match its key")
            if destination.exists():
                destination.unlink()
            os.replace(partial, destination)
        finally:
            partial.unlink(missing_ok=True)
        return destination

    def _object_path(self, sha256: str) -> Path:
        normalized = sha256.casefold()
        if not _SHA256.fullmatch(normalized):
            raise ValueError("content key must be a lowercase SHA-256")
        return self.root / "objects" / normalized[:2] / normalized


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
