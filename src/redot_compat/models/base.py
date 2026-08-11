from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Strict base for versioned public and internal boundary contracts."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, validate_assignment=True)
