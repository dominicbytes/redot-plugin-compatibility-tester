from __future__ import annotations

from pathlib import Path

import pytest

from redot_compat.errors import ConfigurationError
from redot_compat.workspace.install import install_selected_addon


def test_install_selected_addon_only_copies_selected_root(tmp_path: Path) -> None:
    source = tmp_path / "source"
    selected = source / "addons/example"
    selected.mkdir(parents=True)
    (selected / "plugin.cfg").write_text("[plugin]\nname='Example'", encoding="utf-8")
    (source / "outside.txt").write_text("not selected", encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()

    installed = install_selected_addon(source, "addons/example", project)

    assert installed == project / "addons/example"
    assert (installed / "plugin.cfg").is_file()
    assert not (project / "outside.txt").exists()


def test_install_rejects_ambiguous_or_escaping_root(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    project = tmp_path / "project"
    project.mkdir()

    with pytest.raises(ConfigurationError):
        install_selected_addon(source, "../outside", project)
