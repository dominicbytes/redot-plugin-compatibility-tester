from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from redot_compat.models.base import ContractModel
from redot_compat.models.enums import EngineRole, PhaseName, PhaseStatus
from redot_compat.models.finding import Finding


class HarnessEvent(ContractModel):
    schema_version: int = Field(alias="schema", serialization_alias="schema")
    run_id: str
    sequence: int = Field(ge=0)
    event: str
    payload: dict[str, Any] = Field(default_factory=dict)


class PhaseResult(ContractModel):
    phase_name: PhaseName
    engine_role: EngineRole
    command: list[str] = Field(default_factory=list)
    working_directory: str | None = None
    environment_redacted: dict[str, str] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    exit_code: int | None = None
    terminated_by_signal: int | None = None
    timed_out: bool = False
    stdout_path: str | None = None
    stderr_path: str | None = None
    combined_log_path: str | None = None
    sentinel_events: list[HarnessEvent] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    status: PhaseStatus = PhaseStatus.NOT_RUN
