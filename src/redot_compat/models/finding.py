from __future__ import annotations

from redot_compat.models.base import ContractModel
from redot_compat.models.enums import EngineRole, FindingCategory, FindingSeverity, PhaseName


class Finding(ContractModel):
    code: str
    severity: FindingSeverity
    category: FindingCategory
    message: str
    phase: PhaseName | None = None
    engine_role: EngineRole = EngineRole.NONE
    file: str | None = None
    line: int | None = None
    symbol: str | None = None
    raw_log_excerpt: str | None = None
    api_diff_match: str | None = None
    recommendation: str | None = None
