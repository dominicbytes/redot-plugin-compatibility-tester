from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from redot_compat.models import EngineRole, PhaseName, PhaseResult, PhaseStatus
from redot_compat.runner.process import ProcessResult
from redot_compat.testing.host import engine_crashed, run_host_phase

KEY = "ab" * 32


def _line(sequence: int, event: str) -> str:
    body = json.dumps(
        {"schema": 2, "run_id": "test-run", "sequence": sequence, "event": event, "payload": {}}
    )
    mac = hmac.new(bytes.fromhex(KEY), body.encode(), hashlib.sha256).hexdigest()
    return f"REDOT_COMPAT_EVENT {mac} {body}"


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    output: str,
    exit_code: int = 0,
    timed_out: bool = False,
    truncated: bool = False,
    quota: bool = False,
    role: EngineRole = EngineRole.REDOT,
    expect_events: bool = True,
) -> PhaseResult:
    logs = tmp_path / "logs"
    logs.mkdir()
    for name, text in [("stdout", output), ("stderr", ""), ("combined", output)]:
        (logs / f"{name}.log").write_text(text, encoding="utf-8")
    process = ProcessResult(
        command=["engine"],
        working_directory=str(tmp_path),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        duration_ms=1,
        exit_code=exit_code,
        timed_out=timed_out,
        stdout_path=str(logs / "stdout.log"),
        stderr_path=str(logs / "stderr.log"),
        combined_log_path=str(logs / "combined.log"),
        ownership="test",
        stdout_truncated=truncated,
        output_quota_exceeded=quota,
    )
    monkeypatch.setattr("redot_compat.testing.host.run_process", lambda *a, **k: process)
    config = tmp_path / "harness.json"
    config.write_text(
        json.dumps(
            {
                "session_key": KEY,
                "run_id": "test-run",
                "plugin_id": "example",
                "mode": "activate",
                "probes": [],
            }
        )
    )
    return run_host_phase(
        ["engine"],
        phase_name=PhaseName.RUNTIME,
        run_id="test-run",
        working_directory=tmp_path,
        environment={"REDOT_COMPAT_HARNESS_JSON": str(config)},
        log_directory=logs,
        timeout_seconds=10,
        expect_harness_events=expect_events,
        engine_role=role,
    )


def test_harness_pass_cannot_override_engine_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run(
        tmp_path,
        monkeypatch,
        output=_line(0, "start") + "\n" + _line(1, "pass") + "\nERROR: unexpected engine failure",
    )
    assert result.status is PhaseStatus.FAIL
    assert [finding.code for finding in result.findings] == ["UNREVIEWED_ERROR"]


def test_host_phase_preserves_selected_engine_role(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run(
        tmp_path,
        monkeypatch,
        output="ERROR: control failure",
        role=EngineRole.GODOT_CONTROL,
        expect_events=False,
    )
    assert result.engine_role is EngineRole.GODOT_CONTROL
    assert result.findings[0].engine_role is EngineRole.GODOT_CONTROL


@pytest.mark.parametrize("exit_code", [0xC0000005, -1073741819, -11])
def test_crash_after_pass_cannot_be_hidden(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int
) -> None:
    result = _run(
        tmp_path,
        monkeypatch,
        output=_line(0, "start") + "\n" + _line(1, "pass"),
        exit_code=exit_code,
    )
    assert result.status is PhaseStatus.CRASH
    assert "ENGINE_SHUTDOWN_CRASH_AFTER_PASS" in [finding.code for finding in result.findings]


@pytest.mark.parametrize("text", ["CrashHandlerException", "Program crashed with signal 11"])
def test_crash_output_is_decisive(text: str) -> None:
    assert engine_crashed(0, text)
    assert not engine_crashed(1, "ordinary failure")


@pytest.mark.parametrize(
    "output,code,status",
    [
        ("", "HARNESS_INCOMPLETE", PhaseStatus.FAIL),
        (_line(0, "start"), "HARNESS_INCOMPLETE", PhaseStatus.FAIL),
        ('REDOT_COMPAT_EVENT {"event":"pass"}', "HARNESS_EVENT_UNAUTHENTICATED", PhaseStatus.FAIL),
        (
            _line(0, "start") + "\n" + _line(2, "pass"),
            "HARNESS_PROTOCOL_ERROR",
            PhaseStatus.TESTER_ERROR,
        ),
        (
            _line(0, "start") + "\n" + _line(1, "error"),
            "HARNESS_CONFIGURATION_ERROR",
            PhaseStatus.TESTER_ERROR,
        ),
    ],
)
def test_host_distinguishes_incomplete_tampered_and_tester_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output: str,
    code: str,
    status: PhaseStatus,
) -> None:
    result = _run(tmp_path, monkeypatch, output=output)
    assert result.status is status
    assert code in [finding.code for finding in result.findings]


def test_truncated_event_is_not_misreported_as_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run(tmp_path, monkeypatch, output="REDOT_COMPAT_EVENT broken", truncated=True)
    assert result.status is PhaseStatus.FAIL
    assert [finding.code for finding in result.findings] == ["LOG_TRUNCATED"]


def test_timeout_is_not_a_shutdown_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run(tmp_path, monkeypatch, output=_line(0, "start"), exit_code=-9, timed_out=True)
    assert result.status is PhaseStatus.TIMEOUT


def test_missing_config_is_a_tester_error_before_launch(tmp_path: Path) -> None:
    result = run_host_phase(
        ["must-not-launch"],
        phase_name=PhaseName.RUNTIME,
        run_id="test-run",
        working_directory=tmp_path,
        environment={},
        log_directory=tmp_path / "logs",
        timeout_seconds=10,
        expect_harness_events=True,
    )
    assert result.status is PhaseStatus.TESTER_ERROR
    assert result.findings[0].code == "HARNESS_CONFIGURATION_ERROR"


@pytest.mark.parametrize(
    "event,status,code",
    [
        ("REDOT_COMPAT_EVENT forged", PhaseStatus.FAIL, "HARNESS_EVENT_UNAUTHENTICATED"),
        (
            _line(0, "start") + "\n" + _line(2, "pass"),
            PhaseStatus.TESTER_ERROR,
            "HARNESS_PROTOCOL_ERROR",
        ),
        (
            _line(0, "start") + "\n" + _line(1, "error"),
            PhaseStatus.TESTER_ERROR,
            "HARNESS_CONFIGURATION_ERROR",
        ),
    ],
)
def test_untrusted_or_corrupt_evidence_is_not_overridden_by_shutdown_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    event: str,
    status: PhaseStatus,
    code: str,
) -> None:
    result = _run(tmp_path, monkeypatch, output=event, exit_code=0xC0000005)
    assert result.status is status
    assert code in [finding.code for finding in result.findings]


def test_output_quota_exceeded_prevents_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _run(
        tmp_path, monkeypatch, output=_line(0, "start") + "\n" + _line(1, "pass"), quota=True
    )
    assert result.status is PhaseStatus.FAIL
    assert [finding.code for finding in result.findings] == ["LOG_TRUNCATED"]


@pytest.mark.parametrize("terminal", ["pass", "fail"])
@pytest.mark.parametrize("role", [EngineRole.REDOT, EngineRole.GODOT_CONTROL])
@pytest.mark.parametrize("before_pass", [True, False])
def test_crash_marker_must_follow_authenticated_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    before_pass: bool,
    terminal: str,
    role: EngineRole,
) -> None:
    lines = [_line(0, "start"), _line(1, terminal)]
    lines.insert(1 if before_pass else 2, "CrashHandlerException")
    result = _run(tmp_path, monkeypatch, output="\n".join(lines), exit_code=0xC0000005, role=role)
    assert result.status is PhaseStatus.CRASH
    assert (
        f"ENGINE_SHUTDOWN_CRASH_AFTER_{terminal.upper()}" in [f.code for f in result.findings]
    ) is (not before_pass)
