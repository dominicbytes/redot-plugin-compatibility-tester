from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from redot_compat.models import (
    BaselineDecision,
    CompatibilityResult,
    CompatibilityStatus,
    Confidence,
    PluginInventory,
    PolicyResult,
    RecommendedAction,
    SourceKind,
    SourceProvenance,
)


def _source() -> SourceProvenance:
    return SourceProvenance(
        source_kind=SourceKind.LOCAL_DIRECTORY,
        requested_url_or_path="plugin",
        canonical_url="file:///plugin",
        retrieved_at=datetime(2026, 8, 10, tzinfo=UTC),
        archive_sha256="a" * 64,
        archive_size=12,
    )


def test_policy_skip_is_not_tested_compatibility() -> None:
    result = CompatibilityResult(
        run_id="run-test",
        source=_source(),
        inventory=PluginInventory(plugin_roots=["addons/example"], plugin_ids=["example"]),
        policy=PolicyResult(
            baseline_version="4.5.2",
            decision=BaselineDecision.SKIP,
            reason="Decisive target is at the project baseline.",
        ),
        platform="windows-x86_64",
        classification=CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY,
        confidence=Confidence.HIGH,
        confidence_reasons=["Direct project feature evidence."],
        port_candidate=False,
        recommended_next_action=RecommendedAction(code="NONE", text="No port is requested."),
    )

    assert result.classification is CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY
    assert result.policy.dynamic_testing_performed is False
    assert result.phases == []


def test_policy_skip_rejects_dynamic_phases() -> None:
    with pytest.raises(ValidationError, match="policy skip cannot contain dynamic phases"):
        CompatibilityResult.model_validate(
            {
                "run_id": "run-test",
                "source": _source().model_dump(mode="json"),
                "inventory": {"plugin_roots": ["addons/example"]},
                "policy": {
                    "baseline_version": "4.5.2",
                    "decision": "skip",
                    "reason": "baseline",
                },
                "platform": "windows-x86_64",
                "phases": [{"phase_name": "import", "engine_role": "redot"}],
                "classification": "NO_PORT_NEEDED_BASELINE_POLICY",
                "confidence": "high",
                "confidence_reasons": ["direct"],
                "port_candidate": False,
                "recommended_next_action": {"code": "NONE", "text": "none"},
            }
        )


def test_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SourceProvenance.model_validate(
            {
                **_source().model_dump(mode="json"),
                "unexpected": "not part of the public contract",
            }
        )
