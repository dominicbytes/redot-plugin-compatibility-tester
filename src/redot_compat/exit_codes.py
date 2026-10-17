from __future__ import annotations

from redot_compat.constants import ExitCode
from redot_compat.models.enums import CompatibilityStatus

_SUCCESS = frozenset(
    {
        CompatibilityStatus.COMPATIBLE_UNCHANGED,
        CompatibilityStatus.COMPATIBLE_REPACKAGE_ONLY,
    }
)
_INVALID_OR_UPSTREAM = frozenset(
    {
        CompatibilityStatus.INVALID_PACKAGE,
        CompatibilityStatus.UPSTREAM_PACKAGE_FAILURE,
    }
)


def exit_code_for(status: CompatibilityStatus) -> ExitCode:
    """Map a classification to its stable process exit code."""

    if status in _SUCCESS:
        return ExitCode.SUCCESS
    if status is CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY:
        return ExitCode.BASELINE_POLICY_SKIP
    if status.value.startswith("PORT_REQUIRED_") or status is CompatibilityStatus.ENGINE_API_GAP:
        return ExitCode.PORT_REQUIRED
    if status in _INVALID_OR_UPSTREAM:
        return ExitCode.INVALID_OR_UPSTREAM
    if status is CompatibilityStatus.INTERNAL_TESTER_ERROR:
        return ExitCode.INTERNAL_ERROR
    return ExitCode.INCONCLUSIVE
