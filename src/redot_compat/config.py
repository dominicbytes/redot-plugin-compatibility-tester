from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from platformdirs import user_cache_path, user_config_path
from pydantic import Field, SecretStr

from redot_compat.models.base import ContractModel


class ArchiveLimits(ContractModel):
    max_archive_bytes: int = Field(default=512 * 1024 * 1024, gt=0)
    max_expanded_bytes: int = Field(default=2 * 1024 * 1024 * 1024, gt=0)
    max_file_bytes: int = Field(default=512 * 1024 * 1024, gt=0)
    max_entries: int = Field(default=100_000, gt=0)
    max_path_length: int = Field(default=512, gt=0)
    max_depth: int = Field(default=32, gt=0)
    max_expansion_ratio: float = Field(default=200.0, gt=1.0)


class PhaseTimeouts(ContractModel):
    doctor: float = Field(default=30.0, gt=0)
    import_phase: float = Field(default=180.0, gt=0)
    parse: float = Field(default=20.0, gt=0)
    editor: float = Field(default=120.0, gt=0)
    runtime: float = Field(default=120.0, gt=0)
    gui: float = Field(default=180.0, gt=0)
    export: float = Field(default=600.0, gt=0)


class AppConfig(ContractModel):
    output_root: Path = Field(default_factory=lambda: Path.cwd() / "reports")
    cache_root: Path = Field(default_factory=lambda: user_cache_path("redot-compat"))
    config_root: Path = Field(default_factory=lambda: user_config_path("redot-compat"))
    archive_limits: ArchiveLimits = Field(default_factory=ArchiveLimits)
    phase_timeouts: PhaseTimeouts = Field(default_factory=PhaseTimeouts)
    github_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    codeberg_token: SecretStr | None = Field(default=None, exclude=True, repr=False)


def load_config(path: Path | None = None) -> AppConfig:
    if path is None:
        return AppConfig()
    resolved = path.resolve(strict=True)
    data = tomllib.loads(resolved.read_text(encoding="utf-8"))
    values: dict[str, Any] = {}
    paths = data.get("paths", {})
    limits = data.get("limits", {})
    timeouts = data.get("timeouts", {})
    for key in ("output_root", "cache_root", "config_root"):
        if key in paths:
            value = Path(str(paths[key]))
            values[key] = value if value.is_absolute() else resolved.parent / value
    if limits:
        values["archive_limits"] = limits
    if timeouts:
        normalized = {
            "import_phase" if key == "import" else key: value for key, value in timeouts.items()
        }
        values["phase_timeouts"] = normalized
    return AppConfig.model_validate(values)
