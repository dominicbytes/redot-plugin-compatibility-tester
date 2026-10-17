from __future__ import annotations

import os
from pathlib import Path

import pytest

from redot_compat.fsutil import atomic_write_bytes, atomic_write_text


def test_atomic_writes_replace_complete_contents(tmp_path: Path) -> None:
    path = tmp_path / "result.txt"
    path.write_text("old")
    atomic_write_text(path, "caf\u00e9\nsecond\n")
    assert path.read_bytes() == "caf\u00e9\nsecond\n".encode()
    atomic_write_text(path, "caf\u00e9\n", encoding="utf-16")
    assert path.read_bytes() == "caf\u00e9\n".encode("utf-16")
    atomic_write_bytes(path, b"\x00\xff")
    assert path.read_bytes() == b"\x00\xff"
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("failure", ["replace", "fsync"])
def test_atomic_write_failure_preserves_destination_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    path = tmp_path / "result.txt"
    path.write_bytes(b"old")

    def fail(*args: object) -> None:
        raise OSError("simulated failure")

    monkeypatch.setattr(os, failure, fail)
    with pytest.raises(OSError, match="simulated failure"):
        atomic_write_bytes(path, b"new")
    assert path.read_bytes() == b"old"
    assert list(tmp_path.iterdir()) == [path]


def test_atomic_write_fsyncs_before_replacing_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "result.txt"
    events: list[str] = []
    original_replace = os.replace
    original_fsync = os.fsync

    def sync(fd: int) -> None:
        events.append("fsync")
        original_fsync(fd)

    def replace(source: Path, destination: Path) -> None:
        assert source.parent == destination.parent == tmp_path
        assert source.read_bytes() == b"complete\n"
        events.append("replace")
        original_replace(source, destination)

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "replace", replace)
    atomic_write_text(path, "complete\n")
    assert events[:2] == ["fsync", "replace"]
