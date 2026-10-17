from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from redot_compat.errors import HarnessProtocolError
from redot_compat.logs.parser import parse_engine_log, strip_ansi
from redot_compat.logs.sentinel import (
    SENTINEL_PREFIX,
    HarnessUnauthenticatedError,
    parse_harness_events,
)
from redot_compat.models import (
    EngineRole,
    Finding,
    FindingCategory,
    FindingSeverity,
    PhaseName,
    PhaseResult,
    PhaseStatus,
)
from redot_compat.models.phase import HarnessEvent
from redot_compat.runner.process import run_process
from redot_compat.runner.redaction import redact_environment


def engine_crashed(exit_code: int | None, output: str) -> bool:
    return (
        (exit_code is not None and (exit_code < 0 or exit_code >= 0xC0000000))
        or "CrashHandlerException" in output
        or "Program crashed with signal" in output
    )


def run_host_phase(
    command: Sequence[str],
    *,
    phase_name: PhaseName,
    run_id: str,
    working_directory: Path,
    environment: Mapping[str, str],
    log_directory: Path,
    timeout_seconds: float,
    expect_harness_events: bool,
    engine_role: EngineRole = EngineRole.REDOT,
    session_key: str | None = None,
) -> PhaseResult:
    def finding(
        code: str,
        message: str,
        severity: FindingSeverity = FindingSeverity.ERROR,
        category: FindingCategory = FindingCategory.TESTER,
    ) -> Finding:
        return Finding(
            code=code,
            message=message,
            severity=severity,
            category=category,
            phase=phase_name,
            engine_role=engine_role,
        )

    if expect_harness_events:
        try:
            session_key = _read_session_key(environment, run_id, session_key)
        except (OSError, ValueError) as exc:
            return PhaseResult(
                phase_name=phase_name,
                engine_role=engine_role,
                status=PhaseStatus.TESTER_ERROR,
                findings=[finding("HARNESS_CONFIGURATION_ERROR", str(exc))],
            )
    process = run_process(
        command,
        working_directory=working_directory,
        environment=environment,
        output_directory=log_directory,
        timeout_seconds=timeout_seconds,
    )
    stdout = Path(process.stdout_path).read_text(encoding="utf-8", errors="replace")
    stderr = Path(process.stderr_path).read_text(encoding="utf-8", errors="replace")
    output = strip_ansi(stdout + "\n" + stderr)
    findings = parse_engine_log(output, phase=phase_name, engine_role=engine_role)
    events: list[HarnessEvent] = []
    truncated = (
        process.stdout_truncated
        or process.stderr_truncated
        or process.combined_truncated
        or process.output_quota_exceeded
    )
    if truncated:
        findings.append(finding("LOG_TRUNCATED", "Engine output exceeded the retained log limit."))
    protocol_error = False
    if expect_harness_events and not truncated:
        assert session_key is not None
        try:
            events = parse_harness_events(
                output,
                expected_run_id=run_id,
                session_key=session_key,
                require_terminal=False,
            )
        except HarnessUnauthenticatedError as exc:
            findings.append(
                finding(
                    "HARNESS_EVENT_UNAUTHENTICATED",
                    str(exc),
                    FindingSeverity.CRITICAL,
                    FindingCategory.SECURITY,
                )
            )
        except HarnessProtocolError as exc:
            protocol_error = True
            findings.append(finding("HARNESS_PROTOCOL_ERROR", str(exc)))
    terminal = events[-1].event if events else None
    crashed = engine_crashed(process.exit_code, output)
    combined = strip_ansi(
        Path(process.combined_log_path).read_text(encoding="utf-8", errors="replace")
    )
    terminal_offset = combined.rfind(SENTINEL_PREFIX)
    if (
        crashed
        and terminal in {"pass", "fail"}
        and not process.timed_out
        and terminal_offset >= 0
        and not engine_crashed(None, combined[:terminal_offset])
    ):
        findings.append(
            finding(
                f"ENGINE_SHUTDOWN_CRASH_AFTER_{terminal.upper()}",
                f"The engine crashed after authenticated harness {terminal}.",
                FindingSeverity.WARNING,
                FindingCategory.ENGINE,
            )
        )
    if any(item.code == "HARNESS_EVENT_UNAUTHENTICATED" for item in findings):
        status = PhaseStatus.FAIL
    elif process.timed_out:
        status = PhaseStatus.TIMEOUT
    elif protocol_error or terminal == "error":
        status = PhaseStatus.TESTER_ERROR
        if terminal == "error":
            findings.append(
                finding("HARNESS_CONFIGURATION_ERROR", "The harness reported an error.")
            )
    elif crashed:
        status = PhaseStatus.CRASH
    else:
        if (
            expect_harness_events
            and terminal not in {"pass", "fail", "error"}
            and not truncated
            and process.exit_code == 0
            and not any(item.code == "HARNESS_EVENT_UNAUTHENTICATED" for item in findings)
        ):
            findings.append(
                finding("HARNESS_INCOMPLETE", "The harness did not complete the phase.")
            )
        has_error = any(
            item.severity in {FindingSeverity.ERROR, FindingSeverity.CRITICAL} for item in findings
        )
        status = (
            PhaseStatus.PASS
            if process.exit_code == 0
            and not has_error
            and (not expect_harness_events or terminal == "pass")
            else PhaseStatus.FAIL
        )
    return PhaseResult(
        phase_name=phase_name,
        engine_role=engine_role,
        command=process.command,
        working_directory=process.working_directory,
        environment_redacted=redact_environment(environment),
        started_at=process.started_at,
        finished_at=process.finished_at,
        duration_ms=process.duration_ms,
        exit_code=process.exit_code,
        terminated_by_signal=(
            -process.exit_code
            if process.exit_code is not None and -128 < process.exit_code < 0
            else None
        ),
        timed_out=process.timed_out,
        stdout_path=process.stdout_path,
        stderr_path=process.stderr_path,
        combined_log_path=process.combined_log_path,
        sentinel_events=events,
        findings=findings,
        artifacts=[process.stdout_path, process.stderr_path, process.combined_log_path],
        status=status,
    )


def _read_session_key(
    environment: Mapping[str, str],
    run_id: str,
    expected_key: str | None,
) -> str:
    path = environment.get("REDOT_COMPAT_HARNESS_JSON")
    if not path:
        raise ValueError("missing harness.json path")
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("harness.json must contain an object")
    key = config.get("session_key")
    if (
        not isinstance(key, str)
        or re.fullmatch(r"[a-f0-9]{64}", key) is None
        or (expected_key is not None and key != expected_key)
        or config.get("run_id") != run_id
        or config.get("mode") not in ("import", "activate", "canary")
        or not isinstance(config.get("probes"), list)
        or not isinstance(config.get("plugin_id"), str)
    ):
        raise ValueError("invalid harness.json session configuration")
    return key
