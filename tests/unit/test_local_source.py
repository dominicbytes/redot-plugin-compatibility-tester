from __future__ import annotations

from pathlib import Path

import pytest

from redot_compat.errors import SourceResolutionError
from redot_compat.sources.local import acquire_local_source


def test_local_directory_is_copied_and_hashed_without_mutation(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "plugin.cfg").write_text("[plugin]\nname='Example'\n", encoding="utf-8")
    before = (source / "plugin.cfg").read_bytes()

    first = acquire_local_source(source, tmp_path / "run-one")
    second = acquire_local_source(source, tmp_path / "run-two")

    assert first.content_root != source
    assert first.content_sha256 == second.content_sha256
    assert first.provenance.archive_sha256 == first.content_sha256
    assert (source / "plugin.cfg").read_bytes() == before


def test_local_directory_rejects_symlinks(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    link = source / "link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlink creation is unavailable")

    with pytest.raises(SourceResolutionError, match="symbolic link"):
        acquire_local_source(source, tmp_path / "run")


def test_local_archive_is_safely_extracted(tmp_path: Path) -> None:
    import zipfile

    archive = tmp_path / "plugin.zip"
    with zipfile.ZipFile(archive, "w") as value:
        value.writestr("addons/example/plugin.cfg", "[plugin]\nname='Example'\n")

    resolved = acquire_local_source(archive, tmp_path / "run")

    assert (resolved.content_root / "addons/example/plugin.cfg").exists()
    assert resolved.provenance.source_kind.value == "local_archive"
