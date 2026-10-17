from __future__ import annotations

import os
import stat
import sys
from pathlib import Path, PurePosixPath

from redot_compat.errors import WorkerOutputError


def read_worker_text(path: Path, *, root: Path, max_bytes: int) -> str:
    """Read a bounded regular worker file without following links beneath root."""
    if max_bytes < 0:
        raise WorkerOutputError("worker output size limit must be non-negative")
    try:
        base = root.absolute()
        relative = path.absolute().relative_to(base)
        if ".." in relative.parts:
            raise WorkerOutputError("worker output path escapes root")
        current = base
        for part in ("", *relative.parts):
            current = current / part
            metadata = current.lstat()
            if stat.S_ISLNK(metadata.st_mode) or current.is_junction():
                raise WorkerOutputError(
                    f"worker output path contains a symlink or junction: {current}"
                )
        if not path.resolve(strict=True).is_relative_to(base.resolve(strict=True)):
            raise WorkerOutputError("worker output path escapes root")
        descriptor = _open_worker_file(base, relative)
        with os.fdopen(descriptor, "rb") as stream:
            metadata = os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise WorkerOutputError("worker output must be a regular file")
            if metadata.st_size > max_bytes:
                raise WorkerOutputError("worker output exceeds size limit")
            data = stream.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise WorkerOutputError("worker output exceeds size limit")
        return data.decode("utf-8", errors="replace")
    except (OSError, ValueError, RuntimeError) as exc:
        raise WorkerOutputError(f"cannot safely read worker output {path}: {exc}") from exc


def _open_worker_file(root: Path, relative: Path) -> int:
    if sys.platform == "win32":
        return os.open(root / relative, os.O_RDONLY | os.O_BINARY)
    else:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        directory = os.open(root, directory_flags)
        try:
            for component in relative.parts[:-1]:
                child = os.open(component, directory_flags, dir_fd=directory)
                os.close(directory)
                directory = child
            return os.open(
                relative.name or ".", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
        finally:
            os.close(directory)


def translate_worker_path(value: str | None, *, worker_output: Path) -> str | None:
    """Translate an absolute /output POSIX path into the controller's output tree."""
    if value is None:
        return None
    try:
        path = PurePosixPath(value)
        if ".." in path.parts or any(character in value for character in ("\\", "\0", ":")):
            raise WorkerOutputError("unsafe worker output path")
        relative = path.relative_to("/output")
        root = worker_output.resolve()
        translated = root.joinpath(*relative.parts)
        if not translated.resolve().is_relative_to(root):
            raise WorkerOutputError("worker output path escapes root")
        return str(translated)
    except (OSError, ValueError, RuntimeError) as exc:
        raise WorkerOutputError(f"invalid worker output path {value!r}: {exc}") from exc
