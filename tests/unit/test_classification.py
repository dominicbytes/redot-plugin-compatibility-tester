from __future__ import annotations

import pytest

from redot_compat.classify.rules import ClassificationContext, classify
from redot_compat.models import (
    CompatibilityStatus,
    EngineRole,
    Finding,
    FindingCategory,
    FindingSeverity,
    PackageKind,
    PhaseName,
    PhaseResult,
    PhaseStatus,
    PluginInventory,
)


def _phase(
    name: PhaseName, status: PhaseStatus, role: EngineRole = EngineRole.REDOT
) -> PhaseResult:
    return PhaseResult(phase_name=name, engine_role=role, status=status)


def test_tester_error_outranks_timeout_and_plugin_failure() -> None:
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[
                _phase(PhaseName.EDITOR, PhaseStatus.FAIL),
                _phase(PhaseName.RUNTIME, PhaseStatus.TIMEOUT),
                _phase(PhaseName.IMPORT, PhaseStatus.TESTER_ERROR),
            ],
        )
    )

    assert decision.status is CompatibilityStatus.INTERNAL_TESTER_ERROR


def test_phase_failures_map_to_scoped_port_status() -> None:
    editor = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[_phase(PhaseName.EDITOR, PhaseStatus.FAIL)],
        )
    )
    runtime = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[_phase(PhaseName.RUNTIME, PhaseStatus.FAIL)],
        )
    )

    assert editor.status is CompatibilityStatus.PORT_REQUIRED_EDITOR_API
    assert runtime.status is CompatibilityStatus.PORT_REQUIRED_RUNTIME_API
    assert not editor.port_candidate
    assert not runtime.port_candidate


def test_all_selected_redot_phases_pass() -> None:
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[
                _phase(PhaseName.IMPORT, PhaseStatus.PASS),
                _phase(PhaseName.EDITOR, PhaseStatus.PASS),
            ],
        )
    )

    assert decision.status is CompatibilityStatus.COMPATIBLE_UNCHANGED
    assert decision.port_candidate is False


def test_same_failure_under_exact_control_is_upstream_failure() -> None:
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[
                _phase(PhaseName.EDITOR, PhaseStatus.FAIL),
                _phase(PhaseName.EDITOR, PhaseStatus.FAIL, EngineRole.GODOT_CONTROL),
            ],
            exact_control=True,
        )
    )

    assert decision.status is CompatibilityStatus.UPSTREAM_PACKAGE_FAILURE


def test_missing_control_cannot_create_high_confidence_engine_gap() -> None:
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[_phase(PhaseName.IMPORT, PhaseStatus.FAIL)],
            api_gap_direct=True,
            exact_control=False,
        )
    )

    assert decision.status is CompatibilityStatus.PORT_REQUIRED_GDSCRIPT_API
    assert decision.confidence.value != "high"


def test_unreviewed_warning_prevents_compatibility_claim() -> None:
    phase = _phase(PhaseName.RUNTIME, PhaseStatus.PASS)
    phase.findings.append(
        Finding(
            code="UNREVIEWED_WARNING",
            severity=FindingSeverity.WARNING,
            category=FindingCategory.ENGINE,
            message="Unexpected warning.",
            phase=PhaseName.RUNTIME,
            engine_role=EngineRole.REDOT,
        )
    )

    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[phase],
        )
    )

    assert decision.status is CompatibilityStatus.INCONCLUSIVE
    assert decision.action.code == "REVIEW_WARNING"


def test_exact_control_mismatch_is_inconclusive() -> None:
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[
                _phase(PhaseName.RUNTIME, PhaseStatus.PASS),
                _phase(PhaseName.RUNTIME, PhaseStatus.FAIL, EngineRole.GODOT_CONTROL),
            ],
            exact_control=True,
        )
    )

    assert decision.status is CompatibilityStatus.INCONCLUSIVE
    assert decision.action.code == "FIX_CONTROL_FIXTURE"


@pytest.mark.parametrize("redot_status", [PhaseStatus.TIMEOUT, PhaseStatus.CRASH])
def test_exact_control_pass_makes_redot_terminal_failure_a_port_candidate(
    redot_status: PhaseStatus,
) -> None:
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[
                _phase(PhaseName.RUNTIME, redot_status),
                _phase(PhaseName.RUNTIME, PhaseStatus.PASS, EngineRole.GODOT_CONTROL),
            ],
            exact_control=True,
        )
    )

    assert decision.status in {CompatibilityStatus.TIMEOUT, CompatibilityStatus.CRASHED}
    assert decision.confidence.value == "high"
    assert decision.port_candidate is True


@pytest.mark.parametrize(
    "code,action",
    [
        ("HARNESS_EVENT_UNAUTHENTICATED", "REVIEW_PACKAGE_TAMPERING"),
        ("LOG_TRUNCATED", "RAISE_LOG_LIMIT"),
    ],
)
def test_untrustworthy_evidence_prevents_port_advice(code: str, action: str) -> None:
    phase = _phase(PhaseName.RUNTIME, PhaseStatus.FAIL)
    phase.findings.append(
        Finding(
            code=code,
            severity=FindingSeverity.CRITICAL,
            category=FindingCategory.SECURITY,
            message="Evidence is not complete and authentic.",
        )
    )
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[phase],
        )
    )
    assert decision.status is CompatibilityStatus.INCONCLUSIVE
    assert decision.confidence.value == "high"
    assert not decision.port_candidate
    assert decision.action.code == action


@pytest.mark.parametrize(
    "control",
    [
        PhaseStatus.MISSING_CAPABILITY,
        PhaseStatus.CRASH,
        PhaseStatus.TIMEOUT,
        PhaseStatus.TESTER_ERROR,
    ],
)
@pytest.mark.parametrize("redot", [PhaseStatus.PASS, PhaseStatus.FAIL, PhaseStatus.CRASH])
def test_control_infrastructure_failure_is_inconclusive(
    redot: PhaseStatus, control: PhaseStatus
) -> None:
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            exact_control=True,
            phases=[
                _phase(PhaseName.EDITOR, redot),
                _phase(PhaseName.EDITOR, control, EngineRole.GODOT_CONTROL),
            ],
        )
    )
    assert decision.status is CompatibilityStatus.INCONCLUSIVE
    assert not decision.port_candidate


def test_actual_redot_only_failure_is_a_port_candidate() -> None:
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            exact_control=True,
            phases=[
                _phase(PhaseName.EDITOR, PhaseStatus.FAIL),
                _phase(PhaseName.EDITOR, PhaseStatus.PASS, EngineRole.GODOT_CONTROL),
            ],
        )
    )
    assert decision.port_candidate
    assert decision.confidence.value == "high"


@pytest.mark.parametrize("additional_failure", [False, True])
@pytest.mark.parametrize("role", [EngineRole.REDOT, EngineRole.GODOT_CONTROL])
def test_intermittent_shutdown_warning_limits_confidence(
    role: EngineRole, additional_failure: bool
) -> None:
    redot = _phase(PhaseName.EDITOR, PhaseStatus.PASS)
    control = _phase(PhaseName.EDITOR, PhaseStatus.PASS, EngineRole.GODOT_CONTROL)
    phase = redot if role is EngineRole.REDOT else control
    phase.findings = [
        Finding(
            code="ENGINE_INTERMITTENT_SHUTDOWN_CRASH",
            severity=FindingSeverity.WARNING,
            category=FindingCategory.ENGINE,
            message="intermittent post-pass shutdown crash",
        )
    ]
    phases = [redot, control]
    if additional_failure:
        phases.extend(
            [
                _phase(PhaseName.RUNTIME, PhaseStatus.FAIL),
                _phase(PhaseName.RUNTIME, PhaseStatus.PASS, EngineRole.GODOT_CONTROL),
            ]
        )
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=phases,
            exact_control=True,
        )
    )
    assert decision.status is (
        CompatibilityStatus.PORT_REQUIRED_RUNTIME_API
        if additional_failure
        else CompatibilityStatus.COMPATIBLE_UNCHANGED
    )
    assert decision.confidence.value == "medium"
    assert any("intermittent" in reason.lower() for reason in decision.confidence_reasons)
