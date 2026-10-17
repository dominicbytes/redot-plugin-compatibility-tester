from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from redot_compat.errors import WorkerOutputError
from redot_compat.sandbox.worker_output import read_worker_text, translate_worker_path


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")


def test_read_worker_text_decodes_invalid_utf8(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    path.write_bytes(b"safe\xff")
    assert read_worker_text(path, root=tmp_path, max_bytes=5) == "safe\ufffd"


@pytest.mark.parametrize("parent", [False, True])
def test_read_worker_text_rejects_symlinked_file_or_parent(tmp_path: Path, parent: bool) -> None:
    root = tmp_path / "output"
    root.mkdir()
    target = root / "real"
    target.mkdir()
    (target / "result.json").write_text("secret")
    if parent:
        _symlink(root / "link", target)
        path = root / "link/result.json"
    else:
        path = root / "result.json"
        _symlink(path, target / "result.json")
    with pytest.raises(WorkerOutputError, match="symlink or junction"):
        read_worker_text(path, root=root, max_bytes=100)


def test_read_worker_text_rejects_symlinked_root(tmp_path: Path) -> None:
    target = tmp_path / "real"
    target.mkdir()
    (target / "result").write_text("data")
    root = tmp_path / "link"
    _symlink(root, target)
    with pytest.raises(WorkerOutputError, match="symlink or junction"):
        read_worker_text(root / "result", root=root, max_bytes=100)


def test_read_worker_text_rejects_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    path.write_bytes(b"123456")
    with pytest.raises(WorkerOutputError, match="size limit"):
        read_worker_text(path, root=tmp_path, max_bytes=5)


def test_read_worker_text_rejects_directory_missing_and_outside_paths(tmp_path: Path) -> None:
    root = tmp_path / "output"
    root.mkdir()
    (tmp_path / "outside").write_text("data")
    for path in (root, root / "missing", tmp_path / "outside", root / "../outside"):
        with pytest.raises(WorkerOutputError):
            read_worker_text(path, root=root, max_bytes=100)


@pytest.mark.skipif(os.name == "nt", reason="POSIX FIFO")
def test_read_worker_text_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    path = tmp_path / "fifo"
    os.mkfifo(path)
    with pytest.raises(WorkerOutputError, match="regular file"):
        read_worker_text(path, root=tmp_path, max_bytes=100)


def test_translate_worker_path_maps_posix_paths(tmp_path: Path) -> None:
    assert translate_worker_path(None, worker_output=tmp_path) is None
    assert translate_worker_path("/output/logs/out.txt", worker_output=tmp_path) == str(
        tmp_path / "logs/out.txt"
    )


@pytest.mark.parametrize(
    "value",
    [
        "/output/../escape",
        "/output/a/../../escape",
        "/etc/passwd",
        "output/a",
        "/output-other/a",
        "/output/..\\escape",
        "/output/C:/escape",
        "/output/a\0b",
    ],
)
def test_translate_worker_path_rejects_unsafe_paths(tmp_path: Path, value: str) -> None:
    with pytest.raises(WorkerOutputError):
        translate_worker_path(value, worker_output=tmp_path)


def test_translate_worker_path_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "output"
    root.mkdir()
    _symlink(root / "escape", tmp_path)
    with pytest.raises(WorkerOutputError, match="escapes root"):
        translate_worker_path("/output/escape/file", worker_output=root)


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions")
def test_read_worker_text_rejects_junction_parent(tmp_path: Path) -> None:
    root = tmp_path / "output"
    root.mkdir()
    target = root / "real"
    target.mkdir()
    (target / "result").write_text("data")
    link = root / "junction"
    completed = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        pytest.skip("junction creation unavailable")
    assert link.is_junction()
    with pytest.raises(WorkerOutputError, match="symlink or junction"):
        read_worker_text(link / "result", root=root, max_bytes=100)


def test_read_worker_text_bounds_growth_after_fstat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "growing"
    path.write_bytes(b"123")
    original_fstat = os.fstat

    def grow_after_stat(descriptor: int) -> os.stat_result:
        metadata = original_fstat(descriptor)
        with path.open("ab") as stream:
            stream.write(b"456789")
        return metadata

    monkeypatch.setattr(os, "fstat", grow_after_stat)
    with pytest.raises(WorkerOutputError, match="size limit"):
        read_worker_text(path, root=tmp_path, max_bytes=5)
