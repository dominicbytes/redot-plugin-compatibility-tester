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
