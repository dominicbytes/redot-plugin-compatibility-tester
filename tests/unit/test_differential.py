from __future__ import annotations

from redot_compat.classify.differential import DifferentialOutcome, compare_phase_status
from redot_compat.models.enums import PhaseStatus


def test_differential_matrix_is_explicit() -> None:
    assert (
        compare_phase_status(PhaseStatus.FAIL, PhaseStatus.PASS)
        is DifferentialOutcome.REDOT_ONLY_FAILURE
    )
    assert (
        compare_phase_status(PhaseStatus.FAIL, PhaseStatus.FAIL) is DifferentialOutcome.BOTH_FAILED
    )
    assert (
        compare_phase_status(PhaseStatus.PASS, PhaseStatus.FAIL)
        is DifferentialOutcome.CONTROL_MISMATCH
    )
    assert compare_phase_status(PhaseStatus.PASS, None) is DifferentialOutcome.MISSING_CONTROL
