from __future__ import annotations

from packaging.version import Version

from redot_compat.constants import BASELINE_VERSION
from redot_compat.models import (
    BaselineDecision,
    Confidence,
    PluginInventory,
    PolicyResult,
    VersionMeaning,
)


def apply_baseline_policy(
    inventory: PluginInventory,
    *,
    baseline: str = BASELINE_VERSION,
    force_test: bool = False,
) -> PolicyResult:
    target = inventory.effective_api_target
    reason = None
    if target and Version(target).major < 4:
        reason = "Godot 3 targets require a major-version port to Redot's Godot 4 lineage."
    elif any(item.source_type == "dotnet_sdk" for item in inventory.version_evidence):
        reason = (
            "Godot.NET.Sdk must be migrated to Redot.NET.Sdk/26.x before compatibility testing."
        )
    elif any(
        item.meaning is VersionMeaning.DECLARED_MAXIMUM
        and item.confidence in {Confidence.HIGH, Confidence.MEDIUM}
        and item.normalized_version
        and Version(item.normalized_version) < Version(baseline)
        for item in inventory.version_evidence
    ):
        reason = "The GDExtension compatibility maximum is below the Redot baseline."
    elif len(inventory.plugin_roots) > 1:
        reason = "Multiple plugin roots require an explicit plugin selection before a policy skip."
    elif inventory.findings:
        reason = "Package layout or path-safety findings require correction before a policy skip."
    if reason:
        return PolicyResult(
            baseline_version=baseline,
            decision=BaselineDecision.TEST_REQUIRED,
            reason=reason,
            force_test_baseline=force_test,
        )
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
