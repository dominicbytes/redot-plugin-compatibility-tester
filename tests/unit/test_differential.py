from __future__ import annotations

import pytest

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


@pytest.mark.parametrize(
    "control",
    [
        PhaseStatus.TIMEOUT,
        PhaseStatus.CRASH,
        PhaseStatus.MISSING_CAPABILITY,
        PhaseStatus.TESTER_ERROR,
    ],
)
@pytest.mark.parametrize("redot", [PhaseStatus.PASS, PhaseStatus.FAIL, PhaseStatus.CRASH])
def test_unusable_controls_are_not_comparable(redot: PhaseStatus, control: PhaseStatus) -> None:
    assert compare_phase_status(redot, control) is DifferentialOutcome.NOT_COMPARABLE


@pytest.mark.parametrize(
    "redot", [PhaseStatus.TIMEOUT, PhaseStatus.CRASH, PhaseStatus.MISSING_CAPABILITY]
)
def test_both_failed_requires_two_actual_failures(redot: PhaseStatus) -> None:
    assert compare_phase_status(redot, PhaseStatus.FAIL) is DifferentialOutcome.NOT_COMPARABLE
