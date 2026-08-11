from __future__ import annotations

from pydantic import Field

from redot_compat.engines.api_index import ApiIndex
from redot_compat.models.base import ContractModel


class ChangedSymbol(ContractModel):
    symbol: str
    control_signature: str
    candidate_signature: str


class ApiDiff(ContractModel):
    control_engine_version: str | None = None
    candidate_engine_version: str | None = None
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    changed: list[ChangedSymbol] = Field(default_factory=list)


def diff_api_indexes(control: ApiIndex, candidate: ApiIndex) -> ApiDiff:
    control_keys = set(control.symbols)
    candidate_keys = set(candidate.symbols)
    common = sorted(control_keys & candidate_keys)
    return ApiDiff(
        control_engine_version=control.engine_version,
        candidate_engine_version=candidate.engine_version,
        added=sorted(candidate_keys - control_keys),
        removed=sorted(control_keys - candidate_keys),
        changed=[
            ChangedSymbol(
                symbol=key,
                control_signature=control.symbols[key].signature,
                candidate_signature=candidate.symbols[key].signature,
            )
            for key in common
            if control.symbols[key].signature != candidate.symbols[key].signature
        ],
    )
