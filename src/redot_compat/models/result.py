from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import Field, model_validator

from redot_compat.constants import RESULT_SCHEMA_VERSION, VERSION
from redot_compat.models.base import ContractModel
from redot_compat.models.engine import EngineIdentity
from redot_compat.models.enums import BaselineDecision, CompatibilityStatus, Confidence
from redot_compat.models.finding import Finding
from redot_compat.models.inventory import PluginInventory
from redot_compat.models.phase import PhaseResult
from redot_compat.models.source import SourceProvenance


class PolicyResult(ContractModel):
    baseline_version: str
    decision: BaselineDecision
    reason: str
    dynamic_testing_performed: bool = False
    force_test_baseline: bool = False


class RecommendedAction(ContractModel):
    code: str
    text: str


class CompatibilityResult(ContractModel):
    schema_version: str = RESULT_SCHEMA_VERSION
    run_id: str
    source: SourceProvenance
    inventory: PluginInventory
    policy: PolicyResult
    redot_engine: EngineIdentity | None = None
    godot_control_engine: EngineIdentity | None = None
    control_run_available: bool = False
    platform: str
    sandbox: str = "none"
    phases: list[PhaseResult] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    classification: CompatibilityStatus
    confidence: Confidence
    confidence_reasons: list[str] = Field(min_length=1)
    port_candidate: bool
    recommended_next_action: RecommendedAction
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tester_version: str = VERSION
    reproduction: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_policy_semantics(self) -> CompatibilityResult:
        if self.policy.decision is BaselineDecision.SKIP:
            if self.phases or self.policy.dynamic_testing_performed:
                raise ValueError("policy skip cannot contain dynamic phases")
            if self.classification is not CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY:
                raise ValueError("policy skip requires NO_PORT_NEEDED_BASELINE_POLICY")
            if self.port_candidate:
                raise ValueError("policy skip cannot be a port candidate")
        if self.classification is CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY:
            if self.policy.decision is not BaselineDecision.SKIP:
                raise ValueError("baseline classification requires a policy skip")
        return self
