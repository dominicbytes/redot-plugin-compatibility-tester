from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath

from redot_compat.config import ArchiveLimits
from redot_compat.errors import UnsafeArchiveError

_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
_RESERVED_WINDOWS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


@dataclass(frozen=True, slots=True)
class ArchiveEntry:
    raw_name: str
    path: PurePosixPath
    size: int
    compressed_size: int
    is_directory: bool


@dataclass(frozen=True, slots=True)
class ArchiveSummary:
    archive_kind: str
    entry_count: int
    expanded_bytes: int
    compressed_bytes: int


def normalize_member_path(name: str, limits: ArchiveLimits) -> PurePosixPath:
    if "\x00" in name:
        raise UnsafeArchiveError("archive member contains a NUL byte")
    normalized = unicodedata.normalize("NFC", name.replace("\\", "/"))
    if normalized.startswith(("/", "//", "\\?", "\\.")) or _DRIVE_PATH.match(normalized):
        raise UnsafeArchiveError(f"archive member uses an absolute or device path: {name!r}")
    normalized = normalized.removesuffix("/")
    if not normalized:
        raise UnsafeArchiveError("archive member has an empty path")
    if len(normalized) > limits.max_path_length:
        raise UnsafeArchiveError(f"archive path exceeds {limits.max_path_length} characters")
    parts = normalized.split("/")
    if len(parts) > limits.max_depth:
        raise UnsafeArchiveError(f"archive path exceeds nesting depth {limits.max_depth}")
    for part in parts:
        if not part or part in {".", ".."}:
            raise UnsafeArchiveError(
                f"archive member contains traversal or an empty component: {name!r}"
            )
        if part != part.strip() or part.endswith((".", " ")):
            raise UnsafeArchiveError(
                f"archive member contains an ambiguous path component: {name!r}"
            )
        stem = part.split(".", 1)[0].upper()
        if stem in _RESERVED_WINDOWS_NAMES:
            raise UnsafeArchiveError(f"archive member uses a reserved Windows name: {name!r}")
    return PurePosixPath(*parts)


def validate_entries(
    entries: list[ArchiveEntry],
    *,
    limits: ArchiveLimits,
    archive_bytes: int,
) -> ArchiveSummary:
    if len(entries) > limits.max_entries:
        raise UnsafeArchiveError(f"archive contains more than {limits.max_entries} entries")
    seen: dict[str, str] = {}
    expanded = 0
    compressed = 0
    for entry in entries:
        key = unicodedata.normalize("NFC", entry.path.as_posix()).casefold()
        if key in seen:
            raise UnsafeArchiveError(
                f"archive member collision: {seen[key]!r} and {entry.raw_name!r}"
            )
        seen[key] = entry.raw_name
        if entry.size < 0 or entry.compressed_size < 0:
            raise UnsafeArchiveError("archive member reports a negative size")
        if entry.size > limits.max_file_bytes:
            raise UnsafeArchiveError(
                f"archive member {entry.raw_name!r} exceeds {limits.max_file_bytes} bytes"
            )
        expanded += entry.size
        compressed += entry.compressed_size
        if expanded > limits.max_expanded_bytes:
            raise UnsafeArchiveError(f"archive expands beyond {limits.max_expanded_bytes} bytes")
        if entry.size and entry.compressed_size:
            ratio = entry.size / entry.compressed_size
            if ratio > limits.max_expansion_ratio:
                raise UnsafeArchiveError(
                    f"archive member {entry.raw_name!r} exceeds expansion ratio "
                    f"{limits.max_expansion_ratio:g}"
                )
    denominator = max(compressed, archive_bytes, 1)
    if expanded / denominator > limits.max_expansion_ratio:
        raise UnsafeArchiveError(f"archive exceeds expansion ratio {limits.max_expansion_ratio:g}")
    return ArchiveSummary(
        archive_kind="unknown",
        entry_count=len(entries),
        expanded_bytes=expanded,
        compressed_bytes=compressed or archive_bytes,
    )
