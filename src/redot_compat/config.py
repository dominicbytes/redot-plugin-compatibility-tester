from __future__ import annotations

import tomllib
from pathlib import Path

from platformdirs import user_cache_path, user_config_path
from pydantic import AliasChoices, Field, SecretStr

from redot_compat.errors import ConfigurationError
from redot_compat.models.base import ContractModel


class ArchiveLimits(ContractModel):
    max_archive_bytes: int = Field(default=512 * 1024 * 1024, gt=0)
    max_expanded_bytes: int = Field(default=2 * 1024 * 1024 * 1024, gt=0)
    max_file_bytes: int = Field(default=512 * 1024 * 1024, gt=0)
    max_entries: int = Field(default=100_000, gt=0)
    max_path_length: int = Field(default=512, gt=0)
    max_depth: int = Field(default=32, gt=0)
    max_expansion_ratio: float = Field(default=200.0, gt=1.0, allow_inf_nan=False)


class PhaseTimeouts(ContractModel):
    doctor: float = Field(default=30.0, gt=0, allow_inf_nan=False)
    import_phase: float = Field(
        default=180.0,
        gt=0,
        allow_inf_nan=False,
        validation_alias=AliasChoices("import", "import_phase"),
    )
    parse: float = Field(default=20.0, gt=0, allow_inf_nan=False)
    editor: float = Field(default=120.0, gt=0, allow_inf_nan=False)
    runtime: float = Field(default=120.0, gt=0, allow_inf_nan=False)
    gui: float = Field(default=180.0, gt=0, allow_inf_nan=False)
    export: float = Field(default=600.0, gt=0, allow_inf_nan=False)


class AppConfig(ContractModel):
    output_root: Path = Field(default_factory=lambda: Path.cwd() / "reports")
    cache_root: Path = Field(default_factory=lambda: user_cache_path("redot-compat"))
    config_root: Path = Field(default_factory=lambda: user_config_path("redot-compat"))
    archive_limits: ArchiveLimits = Field(default_factory=ArchiveLimits)
    phase_timeouts: PhaseTimeouts = Field(default_factory=PhaseTimeouts)
    github_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    codeberg_token: SecretStr | None = Field(default=None, exclude=True, repr=False)


class _ConfigPaths(ContractModel):
    output_root: Path | None = None
    cache_root: Path | None = None
    config_root: Path | None = None


class _ConfigFile(ContractModel):
    paths: _ConfigPaths = Field(default_factory=_ConfigPaths)
    limits: ArchiveLimits = Field(
        default_factory=ArchiveLimits, validation_alias=AliasChoices("limits", "archive")
    )
    timeouts: PhaseTimeouts = Field(default_factory=PhaseTimeouts)
    github_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    codeberg_token: SecretStr | None = Field(default=None, exclude=True, repr=False)


def load_config(path: Path | None = None) -> AppConfig:
    if path is None:
        return AppConfig()
    try:
        resolved = path.resolve(strict=True)
        config = _ConfigFile.model_validate(tomllib.loads(resolved.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, ValueError):
        # Pydantic/TOML errors may contain the original input, including tokens.
        raise ConfigurationError(
            "Invalid configuration: check the file, TOML keys, types, and positive limits/timeouts."
        ) from None
    result = AppConfig(
        archive_limits=config.limits,
        phase_timeouts=config.timeouts,
        github_token=config.github_token,
        codeberg_token=config.codeberg_token,
    )
    for key in ("output_root", "cache_root", "config_root"):
        value = getattr(config.paths, key)
        if value is not None:
            setattr(result, key, value if value.is_absolute() else resolved.parent / value)
    return result
