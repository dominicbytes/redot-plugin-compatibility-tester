from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from redot_compat.classify import ClassificationContext, classify
from redot_compat.classify.differential import compare_phase_status
from redot_compat.engines.api_diff import diff_api_indexes
from redot_compat.engines.api_index import build_api_index
from redot_compat.engines.doctor import doctor_engine
from redot_compat.models import (
    CompatibilityStatus,
    EngineRole,
    PackageKind,
    PhaseName,
    PhaseResult,
    PhaseStatus,
    PluginInventory,
)
from redot_compat.runner.environment import build_isolated_environment
from redot_compat.sources.local import acquire_local_source
from redot_compat.testing.host import run_host_phase
from redot_compat.testing.service import test_source

ROOT = Path(__file__).resolve().parents[2]
ORACLE = json.loads((ROOT / "tests/gauntlet/oracles/G-05.json").read_text(encoding="utf-8"))
REDOT_SHA256 = "5633d02a28a73514084df6a60ffe01fabdbbb9ac5e28fdfd590ed47277f51989"
GODOT_SHA256 = "446e08f71624052572f96de9031850ba96382ce6752adde38bb955b0a49bed01"


def _option(request: pytest.FixtureRequest, name: str) -> Path:
    value = request.config.getoption(name)
    if not value:
        pytest.skip(f"G-05 requires {name}")
    return Path(value)


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


@pytest.mark.gauntlet
@pytest.mark.integration
def test_g05_exact_control_real_api_gap(request: pytest.FixtureRequest, tmp_path: Path) -> None:
    redot = _option(request, "--integration-redot")
    godot = _option(request, "--integration-godot-control")
    redot_api = _option(request, "--integration-redot-api")
    godot_api = _option(request, "--integration-godot-control-api")
    fixture = ROOT / ORACLE["fixture"]

    redot_source = acquire_local_source(fixture, tmp_path / "redot-source")
    control_source = acquire_local_source(fixture, tmp_path / "control-source")
    assert redot_source.content_sha256 == ORACLE["fixture_sha256"]
    assert control_source.content_sha256 == redot_source.content_sha256

    configuration = {
        "phase": PhaseName.RUNTIME.value,
        "renderer": "gl_compatibility",
        "quit_after": 30,
        "timeout_seconds": 45,
    }
    configuration_sha256 = hashlib.sha256(
        json.dumps(configuration, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert configuration_sha256 == ORACLE["phase_configuration_sha256"]

    redot_phase = run_host_phase(
        [
            str(redot.resolve(strict=True)),
            "--headless",
            "--path",
            str(redot_source.content_root),
            "--quit-after",
            "30",
        ],
        phase_name=PhaseName.RUNTIME,
        run_id="g05-redot",
        working_directory=redot_source.content_root,
        environment=build_isolated_environment(tmp_path / "redot-state"),
        log_directory=tmp_path / "redot-logs",
        timeout_seconds=45,
        expect_harness_events=False,
        engine_role=EngineRole.REDOT,
    )
    control_phase = run_host_phase(
        [
            str(godot.resolve(strict=True)),
            "--headless",
            "--path",
            str(control_source.content_root),
            "--quit-after",
            "30",
        ],
        phase_name=PhaseName.RUNTIME,
        run_id="g05-control",
        working_directory=control_source.content_root,
        environment=build_isolated_environment(tmp_path / "control-state"),
        log_directory=tmp_path / "control-logs",
        timeout_seconds=45,
        expect_harness_events=False,
        engine_role=EngineRole.GODOT_CONTROL,
    )
    expected = ORACLE["expected"]
    assert redot_phase.status.value == expected["redot_status"]
    assert control_phase.status.value == expected["control_status"]
    outcome = compare_phase_status(redot_phase.status, control_phase.status)
    assert outcome.value == expected["differential_outcome"]
    assert any(
        "SpringBoneSimulator3D.BoneDirection" in (finding.raw_log_excerpt or "")
        for finding in redot_phase.findings
    )

    api_diff = diff_api_indexes(
        build_api_index(_load_object(godot_api)),
        build_api_index(_load_object(redot_api)),
    )
    assert ORACLE["api_symbol"] in api_diff.removed

    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.PROJECT),
            phases=[redot_phase, control_phase],
            exact_control=True,
            api_gap_direct=False,
            selected_scope_complete=True,
        )
    )
    assert decision.status.value == expected["classification"]
    assert decision.confidence.value == expected["confidence"]
    assert decision.port_candidate is expected["port_candidate"]

    redot_doctor = doctor_engine(redot, product_hint="redot")
    godot_doctor = doctor_engine(godot, product_hint="godot")
    assert redot_doctor.engine.binary_sha256.casefold() == REDOT_SHA256
    assert godot_doctor.engine.binary_sha256.casefold() == GODOT_SHA256
    assert redot_doctor.engine.compatibility_version == "4.5.2"
    assert godot_doctor.engine.compatibility_version == "4.5.2"

    capture = {
        "gate": ORACLE["gate"],
        "fixture_sha256": redot_source.content_sha256,
        "phase_configuration_sha256": configuration_sha256,
        "redot_engine": redot_doctor.engine.model_dump(mode="json", exclude_none=True),
        "godot_control_engine": godot_doctor.engine.model_dump(mode="json", exclude_none=True),
        "api_symbol": ORACLE["api_symbol"],
        "redot_phase": redot_phase.model_dump(mode="json", exclude_none=True),
        "control_phase": control_phase.model_dump(mode="json", exclude_none=True),
        "differential_outcome": outcome.value,
        "classification": decision.model_dump(mode="json", exclude_none=True),
    }
    (tmp_path / "G-05-capture.json").write_text(
        json.dumps(capture, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


@pytest.mark.gauntlet
@pytest.mark.integration
def test_g05_service_runs_matched_exact_control(
    request: pytest.FixtureRequest, tmp_path: Path
) -> None:
    redot = _option(request, "--integration-redot")
    godot = _option(request, "--integration-godot-control")
    fixture = ROOT / ORACLE["plugin_fixture"]
    result = test_source(
        str(fixture),
        tmp_path / "service-result",
        redot=redot,
        godot_control=godot,
        manifest_path=fixture / "plugin-test.toml",
        backend="host",
        trusted_source=True,
        allow_unsafe_host=True,
        force_test_baseline=True,
    )

    expected = ORACLE["service_expected"]
    assert result.source.archive_sha256 == ORACLE["plugin_fixture_sha256"]
    assert result.classification.value == expected["classification"]
    assert result.confidence.value == expected["confidence"]
    assert result.control_run_available is expected["control_run_available"]
    assert result.godot_control_engine is not None
    assert result.godot_control_engine.binary_sha256.casefold() == GODOT_SHA256
    assert {phase.engine_role for phase in result.phases} == {
        EngineRole.REDOT,
        EngineRole.GODOT_CONTROL,
    }
    redot_phase = next(phase for phase in result.phases if phase.engine_role is EngineRole.REDOT)
    control_phase = next(
        phase for phase in result.phases if phase.engine_role is EngineRole.GODOT_CONTROL
    )
    assert compare_phase_status(redot_phase.status, control_phase.status).value == (
        "redot_only_failure"
    )
    assert not any(
        finding.code == "UNREVIEWED_WARNING"
        for phase in result.phases
        for finding in phase.findings
    )
    assert not any("No exact Godot control" in item for item in result.limitations)


@pytest.mark.gauntlet
@pytest.mark.integration
def test_g05_service_passes_under_both_exact_engines(
    request: pytest.FixtureRequest, tmp_path: Path
) -> None:
    redot = _option(request, "--integration-redot")
    godot = _option(request, "--integration-godot-control")
    fixture = ROOT / ORACLE["pass_fixture"]
    result = test_source(
        str(fixture),
        tmp_path / "pass-result",
        redot=redot,
        godot_control=godot,
        manifest_path=ROOT / "examples/plugin-test.toml",
        backend="host",
        trusted_source=True,
        allow_unsafe_host=True,
        force_test_baseline=True,
    )

    expected = ORACLE["pass_expected"]
    assert result.source.archive_sha256 == ORACLE["pass_fixture_sha256"]
    assert result.classification.value == expected["classification"]
    assert result.confidence.value == expected["confidence"]
    assert result.port_candidate is expected["port_candidate"]
    assert all(phase.status is PhaseStatus.PASS for phase in result.phases)
    assert len(result.phases) == 6


@pytest.mark.gauntlet
def test_g05_complete_classification_matrix() -> None:
    inventory = PluginInventory(package_kind=PackageKind.GDSCRIPT)
    rows = [
        (
            PhaseStatus.PASS,
            PhaseStatus.PASS,
            CompatibilityStatus.COMPATIBLE_UNCHANGED,
            False,
        ),
        (
            PhaseStatus.FAIL,
            PhaseStatus.PASS,
            CompatibilityStatus.PORT_REQUIRED_RUNTIME_API,
            True,
        ),
        (
            PhaseStatus.FAIL,
            PhaseStatus.FAIL,
            CompatibilityStatus.UPSTREAM_PACKAGE_FAILURE,
            False,
        ),
        (
            PhaseStatus.PASS,
            PhaseStatus.FAIL,
            CompatibilityStatus.INCONCLUSIVE,
            False,
        ),
        (
            PhaseStatus.TIMEOUT,
            PhaseStatus.PASS,
            CompatibilityStatus.TIMEOUT,
            True,
        ),
        (
            PhaseStatus.CRASH,
            PhaseStatus.PASS,
            CompatibilityStatus.CRASHED,
            True,
        ),
    ]
    for redot_status, control_status, expected_status, port_candidate in rows:
        decision = classify(
            ClassificationContext(
                inventory=inventory,
                phases=[
                    PhaseResult(
                        phase_name=PhaseName.RUNTIME,
                        engine_role=EngineRole.REDOT,
                        status=redot_status,
                    ),
                    PhaseResult(
                        phase_name=PhaseName.RUNTIME,
                        engine_role=EngineRole.GODOT_CONTROL,
                        status=control_status,
                    ),
                ],
                exact_control=True,
                selected_scope_complete=True,
            )
        )
        assert decision.status is expected_status
        assert decision.port_candidate is port_candidate
