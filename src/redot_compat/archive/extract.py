from __future__ import annotations

import os
import shutil
import stat
import tarfile
import zipfile
from pathlib import Path

from redot_compat.archive.safety import (
    ArchiveEntry,
    ArchiveSummary,
    normalize_member_path,
    validate_entries,
)
from redot_compat.config import ArchiveLimits
from redot_compat.errors import UnsafeArchiveError

_CHUNK_SIZE = 1024 * 1024


def extract_archive(
    archive_path: Path,
    target: Path,
    *,
    limits: ArchiveLimits | None = None,
) -> ArchiveSummary:
    limits = limits or ArchiveLimits()
    archive_path = archive_path.resolve(strict=True)
    if archive_path.stat().st_size > limits.max_archive_bytes:
        raise UnsafeArchiveError(f"archive exceeds {limits.max_archive_bytes} compressed bytes")
    if target.exists():
        raise UnsafeArchiveError("extraction target must be an empty new path")

    if zipfile.is_zipfile(archive_path):
        return _extract_zip(archive_path, target, limits)
    if tarfile.is_tarfile(archive_path):
        return _extract_tar(archive_path, target, limits)
    raise UnsafeArchiveError("input is not a supported ZIP or TAR archive")


def _extract_zip(archive_path: Path, target: Path, limits: ArchiveLimits) -> ArchiveSummary:
    with zipfile.ZipFile(archive_path) as archive:
        entries: list[ArchiveEntry] = []
        info_by_path: list[tuple[zipfile.ZipInfo, Path]] = []
        for info in archive.infolist():
            if info.flag_bits & 0x1:
                raise UnsafeArchiveError(f"encrypted ZIP member is unsupported: {info.filename!r}")
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            kind = stat.S_IFMT(unix_mode) if unix_mode else 0
            if kind == stat.S_IFLNK:
                raise UnsafeArchiveError(f"archive link is forbidden: {info.filename!r}")
            if kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise UnsafeArchiveError(f"archive special file is forbidden: {info.filename!r}")
            normalized_path = normalize_member_path(info.filename, limits)
            is_directory = info.is_dir() or kind == stat.S_IFDIR
            entries.append(
                ArchiveEntry(
                    raw_name=info.filename,
                    path=normalized_path,
                    size=0 if is_directory else info.file_size,
                    compressed_size=info.compress_size,
                    is_directory=is_directory,
                )
            )
            info_by_path.append((info, Path(*normalized_path.parts)))
        summary = validate_entries(
            entries, limits=limits, archive_bytes=archive_path.stat().st_size
        )
        bad_member = archive.testzip()
        if bad_member is not None:
            raise UnsafeArchiveError(f"ZIP CRC check failed for {bad_member!r}")

        target.mkdir(parents=True)
        try:
            written = 0
            for info, relative_path in info_by_path:
                destination = _safe_destination(target, relative_path)
                if info.is_dir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as reader, destination.open("xb") as writer:
                    written += _copy_limited(reader, writer, limits, written)
            return ArchiveSummary(
                archive_kind="zip",
                entry_count=summary.entry_count,
                expanded_bytes=summary.expanded_bytes,
                compressed_bytes=summary.compressed_bytes,
            )
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise


def _extract_tar(archive_path: Path, target: Path, limits: ArchiveLimits) -> ArchiveSummary:
    with tarfile.open(archive_path, mode="r:*") as archive:
        members = archive.getmembers()
        entries: list[ArchiveEntry] = []
        member_by_path: list[tuple[tarfile.TarInfo, Path]] = []
        for member in members:
            if member.issym() or member.islnk():
                raise UnsafeArchiveError(f"archive link is forbidden: {member.name!r}")
            if not (member.isfile() or member.isdir()):
                raise UnsafeArchiveError(f"archive special file is forbidden: {member.name!r}")
            normalized_path = normalize_member_path(member.name, limits)
            try:
                filtered = tarfile.data_filter(member, str(target))
            except (tarfile.FilterError, OSError) as exc:
                raise UnsafeArchiveError(
                    f"TAR data filter rejected {member.name!r}: {exc}"
                ) from exc
            if filtered is None:
                raise UnsafeArchiveError(f"TAR data filter excluded {member.name!r}")
            entries.append(
                ArchiveEntry(
                    raw_name=member.name,
                    path=normalized_path,
                    size=member.size if member.isfile() else 0,
                    compressed_size=0,
                    is_directory=member.isdir(),
                )
            )
            member_by_path.append((member, Path(*normalized_path.parts)))
        summary = validate_entries(
            entries, limits=limits, archive_bytes=archive_path.stat().st_size
        )

        target.mkdir(parents=True)
        try:
            written = 0
            for member, relative_path in member_by_path:
                destination = _safe_destination(target, relative_path)
                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                source = archive.extractfile(member)
                if source is None:
                    raise UnsafeArchiveError(f"could not read TAR member {member.name!r}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                with source, destination.open("xb") as writer:
                    written += _copy_limited(source, writer, limits, written)
            return ArchiveSummary(
                archive_kind="tar",
                entry_count=summary.entry_count,
                expanded_bytes=summary.expanded_bytes,
                compressed_bytes=summary.compressed_bytes,
            )
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise


def _safe_destination(target: Path, relative: Path) -> Path:
    target_resolved = target.resolve()
    destination = (target / relative).resolve()
    if os.path.commonpath((str(target_resolved), str(destination))) != str(target_resolved):
        raise UnsafeArchiveError(f"archive destination escapes extraction root: {relative}")
    return destination


def _copy_limited(
    reader: object, writer: object, limits: ArchiveLimits, already_written: int
) -> int:
    copied = 0
    while chunk := reader.read(_CHUNK_SIZE):  # type: ignore[attr-defined]
        copied += len(chunk)
        if copied > limits.max_file_bytes:
            raise UnsafeArchiveError(
                "archive member exceeded its declared size limit while extracting"
            )
        if already_written + copied > limits.max_expanded_bytes:
            raise UnsafeArchiveError("archive exceeded total size limit while extracting")
        writer.write(chunk)  # type: ignore[attr-defined]
    return copied
