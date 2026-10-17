from __future__ import annotations

from enum import StrEnum

from redot_compat.models.enums import PhaseStatus


class DifferentialOutcome(StrEnum):
    BOTH_PASSED = "both_passed"
    REDOT_ONLY_FAILURE = "redot_only_failure"
    BOTH_FAILED = "both_failed"
    NOT_COMPARABLE = "not_comparable"
    CONTROL_MISMATCH = "control_mismatch"
    MISSING_CONTROL = "missing_control"
    INCONCLUSIVE = "inconclusive"


def compare_phase_status(redot: PhaseStatus, control: PhaseStatus | None) -> DifferentialOutcome:
    if redot is PhaseStatus.NOT_RUN:
        return DifferentialOutcome.INCONCLUSIVE
    if control is None or control is PhaseStatus.NOT_RUN:
        return DifferentialOutcome.MISSING_CONTROL
    if control in {
        PhaseStatus.MISSING_CAPABILITY,
        PhaseStatus.TIMEOUT,
        PhaseStatus.CRASH,
        PhaseStatus.TESTER_ERROR,
    }:
        return DifferentialOutcome.NOT_COMPARABLE
    if redot is PhaseStatus.PASS and control is PhaseStatus.PASS:
        return DifferentialOutcome.BOTH_PASSED
    if redot is PhaseStatus.PASS and control is not PhaseStatus.PASS:
        return DifferentialOutcome.CONTROL_MISMATCH
    if redot is not PhaseStatus.PASS and control is PhaseStatus.PASS:
        return DifferentialOutcome.REDOT_ONLY_FAILURE
    if redot is PhaseStatus.FAIL and control is PhaseStatus.FAIL:
        return DifferentialOutcome.BOTH_FAILED
    return DifferentialOutcome.NOT_COMPARABLE
