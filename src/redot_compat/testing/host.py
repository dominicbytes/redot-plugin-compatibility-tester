from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from redot_compat.errors import HarnessProtocolError
from redot_compat.logs.parser import parse_engine_log
from redot_compat.logs.sentinel import parse_harness_events
from redot_compat.models import (
    EngineRole,
    Finding,
    FindingCategory,
    FindingSeverity,
    PhaseName,
    PhaseResult,
    PhaseStatus,
)
from redot_compat.runner.process import run_process
from redot_compat.runner.redaction import redact_environment


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
) -> PhaseResult:
    process = run_process(
        command,
        working_directory=working_directory,
        environment=environment,
        output_directory=log_directory,
        timeout_seconds=timeout_seconds,
    )
    stdout = Path(process.stdout_path).read_text(encoding="utf-8", errors="replace")
    stderr = Path(process.stderr_path).read_text(encoding="utf-8", errors="replace")
    findings = parse_engine_log(
        stdout + "\n" + stderr,
        phase=phase_name,
        engine_role=engine_role,
    )
    has_error = any(
        item.severity in {FindingSeverity.ERROR, FindingSeverity.CRITICAL} for item in findings
    )
    events = []
    if process.timed_out:
        status = PhaseStatus.TIMEOUT
    elif expect_harness_events:
        try:
            events = parse_harness_events(stdout, expected_run_id=run_id)
        except HarnessProtocolError as exc:
            status = PhaseStatus.TESTER_ERROR
            findings.append(
                Finding(
                    code="HARNESS_PROTOCOL_ERROR",
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.TESTER,
                    message=str(exc),
                    phase=phase_name,
                    engine_role=engine_role,
                )
            )
        else:
            terminal = events[-1].event
            status = (
                PhaseStatus.PASS
                if terminal == "pass" and process.exit_code == 0 and not has_error
                else PhaseStatus.FAIL
            )
    else:
        status = PhaseStatus.PASS if process.exit_code == 0 and not has_error else PhaseStatus.FAIL
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
        timed_out=process.timed_out,
        stdout_path=process.stdout_path,
        stderr_path=process.stderr_path,
        combined_log_path=process.combined_log_path,
        sentinel_events=events,
        findings=findings,
        artifacts=[process.stdout_path, process.stderr_path, process.combined_log_path],
        status=status,
    )
