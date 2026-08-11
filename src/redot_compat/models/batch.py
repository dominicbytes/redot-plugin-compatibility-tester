from __future__ import annotations

from pydantic import Field, field_validator

from redot_compat.models.base import ContractModel


class BatchItem(ContractModel):
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    source: str = Field(min_length=1, max_length=4096)
    ref: str | None = None
    release: str | None = None
    asset: str | None = None
    plugin_id: str | None = None


class BatchManifest(ContractModel):
    schema_version: int = 1
    concurrency: int = Field(default=2, ge=1, le=8)
    items: list[BatchItem] = Field(min_length=1, max_length=10_000)

    @field_validator("items")
    @classmethod
    def unique_item_ids(cls, value: list[BatchItem]) -> list[BatchItem]:
        ids = [item.id.casefold() for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("batch item ids must be unique, including by case")
        return value
