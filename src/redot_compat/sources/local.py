from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path

from redot_compat.archive.extract import extract_archive
from redot_compat.archive.hash import CHUNK_SIZE, copy_and_hash
from redot_compat.config import ArchiveLimits
from redot_compat.errors import SourceResolutionError
from redot_compat.models import SourceKind, SourceProvenance
from redot_compat.sources.base import ResolvedArtifact


def acquire_local_source(
    source: Path,
    run_dir: Path,
    *,
    limits: ArchiveLimits | None = None,
) -> ResolvedArtifact:
    limits = limits or ArchiveLimits()
    source = source.resolve(strict=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    content_root = run_dir / "source"
    if content_root.exists():
        raise SourceResolutionError(f"run source path already exists: {content_root}")

    if source.is_dir():
        digest, size = _copy_directory(source, content_root, limits)
        provenance = _local_provenance(source, SourceKind.LOCAL_DIRECTORY, digest, size)
        return ResolvedArtifact(
            provenance=provenance,
            content_root=content_root,
            content_sha256=digest,
            input_path=content_root,
        )
    if not source.is_file():
        raise SourceResolutionError(f"local source is neither a file nor directory: {source}")

    input_dir = run_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    copied = input_dir / source.name
    try:
        digest, size = copy_and_hash(source, copied, max_bytes=limits.max_archive_bytes)
    except (OSError, ValueError) as exc:
        raise SourceResolutionError(f"could not copy local archive: {exc}") from exc
    provenance = _local_provenance(source, SourceKind.LOCAL_ARCHIVE, digest, size)
    extract_archive(copied, content_root, limits=limits)
    return ResolvedArtifact(
        provenance=provenance,
        content_root=content_root,
        content_sha256=digest,
        input_path=copied,
    )


def local_file_provenance(source: Path) -> SourceProvenance:
    source = source.resolve(strict=True)
    digest = hashlib.sha256()
    size = 0
    with source.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
            size += len(chunk)
    return _local_provenance(source, SourceKind.LOCAL_ARCHIVE, digest.hexdigest(), size)


def _copy_directory(source: Path, target: Path, limits: ArchiveLimits) -> tuple[str, int]:
    digest = hashlib.sha256()
    entry_count = 0
    total_size = 0

    def visit(current: Path, relative: Path) -> None:
        nonlocal entry_count, total_size
        entries = sorted(os.scandir(current), key=lambda item: item.name.casefold())
        for entry in entries:
            entry_count += 1
            if entry_count > limits.max_entries:
                raise SourceResolutionError(
                    f"local directory contains more than {limits.max_entries} entries"
                )
            entry_relative = relative / entry.name
            if len(entry_relative.as_posix()) > limits.max_path_length:
                raise SourceResolutionError("local directory contains an overlong path")
            if len(entry_relative.parts) > limits.max_depth:
                raise SourceResolutionError("local directory exceeds the nesting-depth limit")
            if entry.is_symlink():
                raise SourceResolutionError(
                    f"local directory contains a symbolic link: {entry_relative.as_posix()}"
                )
            source_path = Path(entry.path)
            destination = target / entry_relative
            if entry.is_dir(follow_symlinks=False):
                destination.mkdir(parents=True, exist_ok=True)
                visit(source_path, entry_relative)
                continue
            if not entry.is_file(follow_symlinks=False):
                raise SourceResolutionError(
                    f"local directory contains a special file: {entry_relative.as_posix()}"
                )
            file_size = entry.stat(follow_symlinks=False).st_size
            if file_size > limits.max_file_bytes:
                raise SourceResolutionError(f"local file exceeds size limit: {entry_relative}")
            total_size += file_size
            if total_size > limits.max_expanded_bytes:
                raise SourceResolutionError("local directory exceeds total size limit")
            destination.parent.mkdir(parents=True, exist_ok=True)
            file_digest = hashlib.sha256()
            with source_path.open("rb") as reader, destination.open("xb") as writer:
                while chunk := reader.read(CHUNK_SIZE):
                    file_digest.update(chunk)
                    writer.write(chunk)
            encoded_path = entry_relative.as_posix().encode("utf-8")
            digest.update(len(encoded_path).to_bytes(4, "big"))
            digest.update(encoded_path)
            digest.update(file_size.to_bytes(8, "big"))
            digest.update(file_digest.digest())

    target.mkdir(parents=True)
    try:
        visit(source, Path())
    except Exception:
        import shutil

        shutil.rmtree(target, ignore_errors=True)
        raise
    return digest.hexdigest(), total_size


def _local_provenance(
    source: Path, source_kind: SourceKind, digest: str, size: int
) -> SourceProvenance:
    return SourceProvenance(
        source_kind=source_kind,
        requested_url_or_path=str(source),
        canonical_url=source.as_uri(),
        host="localhost",
        retrieved_at=datetime.now(UTC),
        archive_sha256=digest,
        archive_size=size,
    )
