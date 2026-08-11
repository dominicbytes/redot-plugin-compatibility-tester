from __future__ import annotations

import hashlib
from pathlib import Path

from redot_compat.cache.store import ContentStore


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
