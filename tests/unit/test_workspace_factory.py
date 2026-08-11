from __future__ import annotations

from pathlib import Path

from redot_compat.workspace.factory import cleanup_workspace, create_workspace


def test_workspace_is_unique_owned_and_cleanup_is_idempotent(tmp_path: Path) -> None:
    first = create_workspace(tmp_path)
    second = create_workspace(tmp_path)

    assert first.root != second.root
    assert first.marker.is_file()
    assert first.source.is_relative_to(first.root)
    cleanup_workspace(first)
    cleanup_workspace(first)
    assert not first.root.exists()
    assert second.root.exists()
