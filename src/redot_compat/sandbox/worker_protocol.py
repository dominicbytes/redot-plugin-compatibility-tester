from __future__ import annotations

from pathlib import PurePosixPath

from pydantic import Field, field_validator

from redot_compat.models.base import ContractModel
from redot_compat.models.enums import PhaseName
from redot_compat.models.manifest import PluginTestManifest


class WorkerRequest(ContractModel):
    protocol_version: int = 1
    run_id: str = Field(pattern=r"^run-[a-f0-9]{32}$")
    source_subpath: str
    phases: list[PhaseName] = Field(min_length=1)
    engine_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest: PluginTestManifest | None = None
    output_subpath: str = "result"

    @field_validator("source_subpath")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value.replace("\\", "/"))
        if value == ".":
            return value
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("source_subpath must be a safe relative path")
        return path.as_posix()

    @field_validator("output_subpath")
    @classmethod
    def validate_output_path(cls, value: str) -> str:
        path = PurePosixPath(value.replace("\\", "/"))
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError("output_subpath must be a safe relative path")
        return path.as_posix()

    @field_validator("phases")
    @classmethod
    def validate_phases(cls, value: list[PhaseName]) -> list[PhaseName]:
        if len(value) != len(set(value)):
            raise ValueError("worker phases cannot repeat")
        return value
