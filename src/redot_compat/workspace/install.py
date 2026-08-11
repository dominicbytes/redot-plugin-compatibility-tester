from __future__ import annotations

import shutil
from pathlib import Path, PurePosixPath

from redot_compat.errors import ConfigurationError


def install_selected_addon(source_root: Path, plugin_root: str, project_root: Path) -> Path:
    relative = PurePosixPath(plugin_root.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) < 2:
        raise ConfigurationError("plugin root must be a relative addons/<id> path")
    if relative.parts[0] != "addons" or any(part in {"", "."} for part in relative.parts):
        raise ConfigurationError("plugin root must be inside addons")
    source_base = source_root.resolve(strict=True)
    selected = (source_base / Path(*relative.parts)).resolve(strict=True)
    if not selected.is_dir() or not selected.is_relative_to(source_base):
        raise ConfigurationError("selected plugin root is missing or escapes the source")
    if any(path.is_symlink() for path in selected.rglob("*")):
        raise ConfigurationError("selected plugin root contains a symbolic link")
    project = project_root.resolve(strict=True)
    destination = project / "addons" / selected.name
    if destination.exists():
        raise ConfigurationError(f"fixture destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(selected, destination, symlinks=False)
    return destination
