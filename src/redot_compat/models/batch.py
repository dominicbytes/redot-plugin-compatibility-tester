from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any

from pydantic import Field, WithJsonSchema, field_validator

from redot_compat.constants import BATCH_SCHEMA_VERSION
from redot_compat.models.base import ContractModel
from redot_compat.models.enums import CompatibilityStatus

_SCHEMA_VERSION_PATTERN = r"^1\.[0-9]+\.[0-9]+$"
_LEGACY_SCHEMA_VERSION = 1

# Manifests written before the semver switch used ``schema_version = 1``; it is
# still accepted (and normalized to the current string) so existing TOML keeps
# working. Any other major version is rejected.
BatchSchemaVersion = Annotated[
    str,
    WithJsonSchema(
        {
            "anyOf": [
                {"type": "string", "pattern": _SCHEMA_VERSION_PATTERN},
                {"type": "integer", "const": _LEGACY_SCHEMA_VERSION},
            ]
        }
    ),
]


class BatchItem(ContractModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    source: str = Field(min_length=1, max_length=4096)
    ref: str | None = None
    release: str | None = None
    asset: str | None = None
    plugin_id: str | None = None


class BatchManifest(ContractModel):
    schema_version: BatchSchemaVersion = BATCH_SCHEMA_VERSION
    concurrency: int = Field(default=2, ge=1, le=8)
    items: list[BatchItem] = Field(min_length=1, max_length=10_000)

    @field_validator("schema_version", mode="before")
    @classmethod
    def supported_schema_version(cls, value: Any) -> Any:
        if isinstance(value, int) and not isinstance(value, bool):
            if value == _LEGACY_SCHEMA_VERSION:
                return BATCH_SCHEMA_VERSION
            raise ValueError(f"unsupported batch schema_version: {value}")
        if isinstance(value, str) and not re.fullmatch(_SCHEMA_VERSION_PATTERN, value):
            raise ValueError(f"unsupported batch schema_version: {value!r}")
        return value

    @field_validator("items")
    @classmethod
    def unique_item_ids(cls, value: list[BatchItem]) -> list[BatchItem]:
        ids = [item.id.casefold() for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("batch item ids must be unique, including by case")
        return value


class BatchItemState(StrEnum):
    COMPLETED = "completed"
    RESUMED = "resumed"
    FAILED = "failed"
    PENDING = "pending"


class BatchItemOutcome(ContractModel):
    id: str
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    state: BatchItemState
    classification: CompatibilityStatus | None = None
    error_type: str | None = None


class BatchSummary(ContractModel):
    schema_version: str = BATCH_SCHEMA_VERSION
    complete: bool = False
    interrupted: bool = False
    total: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    resumed: int = Field(ge=0)
    pending: int = Field(default=0, ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    items: list[BatchItemOutcome] = Field(default_factory=list)
