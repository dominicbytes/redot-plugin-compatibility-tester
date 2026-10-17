from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from redot_compat.cache.store import ContentStore
from redot_compat.errors import SourceResolutionError


def test_content_store_is_atomic_and_rejects_corrupt_reuse(tmp_path: Path) -> None:
    source = tmp_path / "source.zip"
    source.write_bytes(b"content")
    digest = hashlib.sha256(b"content").hexdigest()
    store = ContentStore(tmp_path / "cache")

    first = store.put_file(source, expected_sha256=digest)
    second = store.put_file(source, expected_sha256=digest)

    assert first == second
    assert first.read_bytes() == b"content"
    first.write_bytes(b"corrupt")
    assert store.get_file(digest) is None


def test_replace_keeps_corrupt_destination_until_atomic_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"valid")
    digest = hashlib.sha256(b"valid").hexdigest()
    store = ContentStore(tmp_path / "cache")
    destination = store.put_file(source, expected_sha256=digest)
    destination.write_bytes(b"broken")
    original_replace = os.replace

    def replace(partial: Path, target: Path) -> None:
        assert target == destination
        assert target.read_bytes() == b"broken"
        original_replace(partial, target)

    monkeypatch.setattr(os, "replace", replace)
    assert store.put_file(source, expected_sha256=digest).read_bytes() == b"valid"


def test_verification_can_be_skipped(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.write_bytes(b"valid")
    digest = hashlib.sha256(b"valid").hexdigest()
    store = ContentStore(tmp_path / "cache")
    destination = store.put_file(source, expected_sha256=digest)
    destination.write_bytes(b"broken")
    assert store.get_file(digest, verify=False) == destination
    assert store.get_file(digest) is None


def test_put_evicts_least_recently_used_and_prune_enforces_limit(tmp_path: Path) -> None:
    store = ContentStore(tmp_path / "cache", max_bytes=8)
    paths: list[Path] = []
    for content in (b"aaaa", b"bbbb"):
        source = tmp_path / content.decode()
        source.write_bytes(content)
        paths.append(store.put_file(source, expected_sha256=hashlib.sha256(content).hexdigest()))
    for path in paths:
        os.utime(path, ns=(1, 1))
    assert store.get_file(paths[0].name) == paths[0]
    source = tmp_path / "third"
    source.write_bytes(b"cccc")
    third = store.put_file(source, expected_sha256=hashlib.sha256(b"cccc").hexdigest())
    assert paths[0].is_file()
    assert not paths[1].exists()
    assert third.is_file()
    assert store.total_bytes() == 8
    assert set(store.prune(max_bytes=0)) == {paths[0], third}
    assert store.total_bytes() == 0


def test_oversized_input_and_negative_limits_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ContentStore(tmp_path / "invalid", max_bytes=-1)
    store = ContentStore(tmp_path / "cache", max_bytes=0)
    source = tmp_path / "source"
    source.write_bytes(b"large")
    with pytest.raises(SourceResolutionError, match="exceeds max_bytes"):
        store.put_file(source, expected_sha256=hashlib.sha256(b"large").hexdigest())
    with pytest.raises(ValueError, match="non-negative"):
        store.prune(max_bytes=-1)
    assert store.total_bytes() == 0
