from __future__ import annotations

from packaging.version import Version

from redot_compat.constants import BASELINE_VERSION
from redot_compat.models import BaselineDecision, Confidence, PluginInventory, PolicyResult


def apply_baseline_policy(
    inventory: PluginInventory,
    *,
    baseline: str = BASELINE_VERSION,
    force_test: bool = False,
) -> PolicyResult:
    target = inventory.effective_api_target
    if not target:
        return PolicyResult(
            baseline_version=baseline,
            decision=BaselineDecision.UNKNOWN,
            reason="No authoritative effective API target was found.",
            force_test_baseline=force_test,
        )
    if inventory.version_conflicts:
        return PolicyResult(
            baseline_version=baseline,
            decision=BaselineDecision.TEST_REQUIRED,
            reason="Conflicting version evidence requires a scoped dynamic test.",
            force_test_baseline=force_test,
        )
    at_or_below = Version(target) <= Version(baseline)
    if at_or_below and force_test:
        return PolicyResult(
            baseline_version=baseline,
            decision=BaselineDecision.FORCED_TEST,
            reason=f"Target {target} is within baseline, but testing was explicitly forced.",
            force_test_baseline=True,
        )
    if at_or_below and inventory.effective_api_confidence in {
        Confidence.HIGH,
        Confidence.MEDIUM,
    }:
        return PolicyResult(
            baseline_version=baseline,
            decision=BaselineDecision.SKIP,
            reason=(
                f"Authoritative target {target} is at or below baseline {baseline}; "
                "dynamic testing was skipped by policy, not passed."
            ),
        )
    if at_or_below:
        return PolicyResult(
            baseline_version=baseline,
            decision=BaselineDecision.UNKNOWN,
            reason="Only low-confidence baseline evidence is available.",
            force_test_baseline=force_test,
        )
    return PolicyResult(
        baseline_version=baseline,
        decision=BaselineDecision.TEST_REQUIRED,
        reason=f"Effective target {target} is newer than baseline {baseline}.",
        force_test_baseline=force_test,
    )
