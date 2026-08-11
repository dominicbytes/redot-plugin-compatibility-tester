from __future__ import annotations

from redot_compat.inspect.baseline import apply_baseline_policy
from redot_compat.models import BaselineDecision, Confidence, PluginInventory


def test_decisive_target_at_baseline_skips_dynamic_testing() -> None:
    inventory = PluginInventory(
        effective_api_target="4.5.2", effective_api_confidence=Confidence.HIGH
    )

    policy = apply_baseline_policy(inventory)

    assert policy.decision is BaselineDecision.SKIP
    assert policy.dynamic_testing_performed is False


def test_newer_unknown_and_conflicted_targets_require_testing() -> None:
    newer = PluginInventory(effective_api_target="4.6", effective_api_confidence=Confidence.HIGH)
    unknown = PluginInventory()
    conflicted = PluginInventory(
        effective_api_target="4.5", version_conflicts=["direct evidence disagrees"]
    )

    assert apply_baseline_policy(newer).decision is BaselineDecision.TEST_REQUIRED
    assert apply_baseline_policy(unknown).decision is BaselineDecision.UNKNOWN
    assert apply_baseline_policy(conflicted).decision is BaselineDecision.TEST_REQUIRED


def test_force_flag_preserves_baseline_evidence_but_requests_testing() -> None:
    inventory = PluginInventory(
        effective_api_target="4.5", effective_api_confidence=Confidence.HIGH
    )

    policy = apply_baseline_policy(inventory, force_test=True)

    assert policy.decision is BaselineDecision.FORCED_TEST
    assert policy.force_test_baseline is True
