from __future__ import annotations

import re
import shutil
import uuid
from pathlib import Path

from redot_compat.errors import ConfigurationError
from redot_compat.models.base import ContractModel

_RUN_ID = re.compile(r"^run-[a-f0-9]{32}$")
_MARKER_NAME = ".redot-compat-owned-run"


class Workspace(ContractModel):
    run_id: str
    base_root: Path
    root: Path
    marker: Path
    source: Path
    project: Path
    state: Path
    logs: Path
    output: Path


def create_workspace(base_root: Path, *, run_id: str | None = None) -> Workspace:
    base = base_root.resolve()
    base.mkdir(parents=True, exist_ok=True)
    selected_id = run_id or f"run-{uuid.uuid4().hex}"
    if not _RUN_ID.fullmatch(selected_id):
        raise ConfigurationError("run_id must use the generated run-<32 hex> form")
    root = base / selected_id
    root.mkdir(exist_ok=False)
    marker = root / _MARKER_NAME
    marker.write_text(selected_id + "\n", encoding="utf-8", newline="\n")
    paths = {name: root / name for name in ("source", "project", "state", "logs", "output")}
    for path in paths.values():
        path.mkdir()
    return Workspace(
        run_id=selected_id,
        base_root=base,
        root=root,
        marker=marker,
        **paths,
    )


def cleanup_workspace(workspace: Workspace) -> None:
    if not workspace.root.exists():
        return
    root = workspace.root.resolve(strict=True)
    base = workspace.base_root.resolve(strict=True)
    if root.parent != base or not _RUN_ID.fullmatch(root.name):
        raise ConfigurationError("refusing to clean a path outside the owned workspace root")
    marker = root / _MARKER_NAME
    if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != workspace.run_id:
        raise ConfigurationError("refusing to clean a workspace without its ownership marker")
    shutil.rmtree(root)
