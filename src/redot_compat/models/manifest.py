from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

from pydantic import Field, field_validator, model_validator

from redot_compat.models.base import ContractModel
from redot_compat.models.enums import PhaseName


class ProbeType(StrEnum):
    CLASS_EXISTS = "class_exists"
    RESOURCE_EXISTS = "resource_exists"
    NODE_EXISTS = "node_exists"


class Probe(ContractModel):
    type: ProbeType
    value: str = Field(min_length=1, max_length=512)
    expected: bool = True

    @model_validator(mode="after")
    def validate_probe_value(self) -> Probe:
        if self.type is ProbeType.CLASS_EXISTS:
            if not self.value.replace("_", "a").isalnum() or self.value[0].isdigit():
                raise ValueError("class probe value must be an identifier")
        elif self.type is ProbeType.RESOURCE_EXISTS:
            if not self.value.startswith("res://"):
                raise ValueError("resource probe must use res://")
            path = PurePosixPath(self.value.removeprefix("res://"))
            if not path.parts or any(part in {"", ".", ".."} for part in path.parts):
                raise ValueError("resource probe must stay inside res://")
        else:
            path = PurePosixPath(self.value.replace("\\", "/"))
            if path.is_absolute() or any(part in {"", ".."} for part in path.parts):
                raise ValueError("node probe must be a safe relative NodePath")
        return self


class PluginTestManifest(ContractModel):
    schema_version: int = 1
    plugin_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    phases: list[PhaseName] = Field(
        default_factory=lambda: [PhaseName.IMPORT, PhaseName.EDITOR, PhaseName.RUNTIME]
    )
    probes: list[Probe] = Field(default_factory=list, max_length=128)
    timeout_seconds: int = Field(default=120, ge=1, le=600)

    @field_validator("phases")
    @classmethod
    def validate_phases(cls, value: list[PhaseName]) -> list[PhaseName]:
        allowed = {
            PhaseName.IMPORT,
            PhaseName.PARSE,
            PhaseName.EDITOR,
            PhaseName.RUNTIME,
            PhaseName.GUI,
            PhaseName.EXPORT,
        }
        if not value or len(value) != len(set(value)) or any(item not in allowed for item in value):
            raise ValueError("manifest phases must be unique supported plugin phases")
        return value

    def to_harness_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)
