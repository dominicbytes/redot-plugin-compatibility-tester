from __future__ import annotations

import hashlib
import json
import re
import secrets
import shutil
import tomllib
import uuid
from pathlib import Path

from redot_compat.classify import ClassificationContext, classify
from redot_compat.config import ArchiveLimits, PhaseTimeouts
from redot_compat.engines.doctor import DoctorReport, doctor_engine
from redot_compat.errors import ConfigurationError
from redot_compat.inspect.service import inspect_source
from redot_compat.logs.parser import strip_ansi
from redot_compat.models import (
    BaselineDecision,
    CompatibilityResult,
    CompatibilityStatus,
    EngineRole,
    Finding,
    FindingCategory,
    FindingSeverity,
    PhaseName,
    PhaseResult,
    PhaseStatus,
    PluginTestManifest,
    PolicyResult,
)
from redot_compat.reports import write_reports
from redot_compat.runner.environment import build_isolated_environment
from redot_compat.sandbox.base import Backend, BackendSelection, select_backend
from redot_compat.sandbox.docker_linux import (
    DockerProfile,
    build_docker_command,
    docker_daemon_available,
    prepare_heartbeat,
    run_docker_command,
)
from redot_compat.sandbox.worker_output import read_worker_text, translate_worker_path
from redot_compat.sandbox.worker_protocol import WorkerRequest
from redot_compat.testing.host import run_host_phase
from redot_compat.workspace import Workspace, create_workspace, install_selected_addon

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE_HARNESS = Path(__file__).resolve().parents[1] / "harness"
_HARNESS_ROOT = _PACKAGE_HARNESS if _PACKAGE_HARNESS.is_dir() else _PROJECT_ROOT / "harness"
_BASE_HARNESS = _HARNESS_ROOT / "base_project"
_EDITOR_HARNESS = _HARNESS_ROOT / "editor_plugin"


def run_compatibility_test(
    source: str,
    output: Path,
    *,
    redot: Path | None = None,
    godot_control: Path | None = None,
    worker_image: str | None = None,
    worker_engine_sha256: str | None = None,
    manifest_path: Path | None = None,
    requested_ref: str | None = None,
    release: str | None = None,
    asset_pattern: str | None = None,
    plugin_id: str | None = None,
    backend: str = "auto",
    trusted_source: bool = False,
    allow_unsafe_host: bool = False,
    force_test_baseline: bool = False,
    archive_limits: ArchiveLimits | None = None,
    phase_timeouts: PhaseTimeouts | None = None,
    github_token: str | None = None,
    codeberg_token: str | None = None,
) -> CompatibilityResult:
    output_path = output.resolve()
    if output_path.exists() and any(output_path.iterdir()):
        raise ValueError(f"output directory must be new or empty: {output_path}")
    output_path.mkdir(parents=True, exist_ok=True)
    static_output = output_path / "static"
    static_result = inspect_source(
        source,
        static_output,
        requested_ref=requested_ref,
        release=release,
        asset_pattern=asset_pattern,
        plugin_id=plugin_id,
        force_test_baseline=force_test_baseline,
        archive_limits=archive_limits,
        github_token=github_token,
        codeberg_token=codeberg_token,
    )
    if static_result.classification in {
        CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY,
        CompatibilityStatus.INVALID_PACKAGE,
        CompatibilityStatus.PORT_REQUIRED_MAJOR_UPGRADE,
    } or (
        static_result.classification is CompatibilityStatus.INCONCLUSIVE
        and len(static_result.inventory.plugin_roots) != 1
    ):
        write_reports(static_result, output_path)
        return static_result

    if (worker_image is None) is not (worker_engine_sha256 is None):
        raise ConfigurationError(
            "Docker execution requires both --worker-image and --worker-engine-sha256"
        )
    docker_profile = DockerProfile(image=worker_image) if worker_image is not None else None
    docker_eligible = False
    if docker_profile is not None:
        docker_eligible, _docker_detail = docker_daemon_available()
    selection = select_backend(
        backend,
        docker_eligible=docker_eligible,
        trusted_source=trusted_source,
        allow_unsafe_host=allow_unsafe_host,
    )
    if selection.backend is Backend.NONE:
        result = _missing_backend_result(static_result, selection)
        write_reports(result, output_path)
        return result
    source_root = static_output / "workspace/source"
    plugin_root = static_result.inventory.plugin_roots[0]
    plugin_name = Path(plugin_root).name
    manifest = _load_manifest(manifest_path, static_result, plugin_name)
    if manifest.plugin_id != plugin_name:
        raise ConfigurationError(
            f"manifest plugin_id {manifest.plugin_id!r} does not match selected {plugin_name!r}"
        )
    if selection.backend is Backend.DOCKER_LINUX:
        if godot_control is not None:
            raise ConfigurationError("the Linux worker does not contain an exact Godot control")
        assert docker_profile is not None
        assert worker_engine_sha256 is not None
        result = _run_docker_backend(
            static_result,
            output_path,
            source_root,
            manifest,
            docker_profile,
            worker_engine_sha256,
            phase_timeouts,
            archive_limits,
        )
        write_reports(result, output_path)
        return result
    if redot is None:
        result = _missing_backend_result(
            static_result,
            BackendSelection(
                backend=Backend.NONE,
                reason="trusted host execution requires an explicit --redot binary",
            ),
        )
        write_reports(result, output_path)
        return result

    timeouts = phase_timeouts or PhaseTimeouts()
    doctor, control_doctor = _doctor_engines(redot, godot_control, timeouts)
    canary_phases: list[PhaseResult] = []
    retry_attempts: list[PhaseResult] = []
    workspace, environment = _prepare_engine_run(
        output_path / "runs/redot",
        source_root,
        plugin_root,
    )
    phases = _run_selected_phases(
        redot.resolve(strict=True),
        workspace,
        environment,
        manifest,
        EngineRole.REDOT,
        phase_timeouts=timeouts,
        canary_phases=canary_phases,
        retry_attempts=retry_attempts,
    )
    if godot_control is not None:
        control_workspace, control_environment = _prepare_engine_run(
            output_path / "runs/godot-control",
            source_root,
            plugin_root,
        )
        phases.extend(
            _run_selected_phases(
                godot_control.resolve(strict=True),
                control_workspace,
                control_environment,
                manifest,
                EngineRole.GODOT_CONTROL,
                phase_timeouts=timeouts,
                canary_phases=canary_phases,
                retry_attempts=retry_attempts,
            )
        )
    return _host_result(
        static_result,
        output_path,
        workspace,
        doctor,
        control_doctor,
        manifest,
        phases,
        canary_phases,
        retry_attempts,
    )


def _doctor_engines(
    redot: Path,
    godot_control: Path | None,
    timeouts: PhaseTimeouts,
) -> tuple[DoctorReport, DoctorReport | None]:
    control = (
        doctor_engine(godot_control, product_hint="godot", timeout_seconds=timeouts.doctor)
        if godot_control is not None
        else None
    )
    doctor = doctor_engine(redot, product_hint="redot", timeout_seconds=timeouts.doctor)
    if (
        control is not None
        and control.engine.compatibility_version != doctor.engine.compatibility_version
    ):
        raise ConfigurationError(
            "Godot control compatibility version must exactly match the Redot target "
            f"({doctor.engine.compatibility_version}); got {control.engine.compatibility_version}"
        )
    return doctor, control


def _host_result(
    static_result: CompatibilityResult,
    output_path: Path,
    workspace: Workspace,
    doctor: DoctorReport,
    control_doctor: DoctorReport | None,
    manifest: PluginTestManifest,
    phases: list[PhaseResult],
    canary_phases: list[PhaseResult],
    retry_attempts: list[PhaseResult],
) -> CompatibilityResult:
    selected_scope_complete = (
        static_result.inventory.contains_editor_plugin and PhaseName.EDITOR in manifest.phases
    ) or (bool(manifest.probes) and PhaseName.RUNTIME in manifest.phases)
    decision = classify(
        ClassificationContext(
            inventory=static_result.inventory,
            phases=phases,
            exact_control=control_doctor is not None,
            selected_scope_complete=selected_scope_complete,
        )
    )
    policy = PolicyResult(
        baseline_version=static_result.policy.baseline_version,
        decision=(
            BaselineDecision.FORCED_TEST
            if static_result.policy.decision is BaselineDecision.SKIP
            else static_result.policy.decision
        ),
        reason=static_result.policy.reason,
        dynamic_testing_performed=True,
        force_test_baseline=static_result.policy.force_test_baseline,
    )
    result = CompatibilityResult(
        run_id=workspace.run_id,
        source=static_result.source,
        inventory=static_result.inventory,
        policy=policy,
        redot_engine=doctor.engine,
        godot_control_engine=(control_doctor.engine if control_doctor is not None else None),
        control_run_available=control_doctor is not None,
        platform=static_result.platform,
        sandbox=Backend.TRUSTED_HOST.value,
        phases=phases,
        engine_canary_phases=canary_phases,
        phase_retry_attempts=retry_attempts,
        findings=[finding for phase in phases for finding in phase.findings],
        classification=decision.status,
        confidence=decision.confidence,
        confidence_reasons=decision.confidence_reasons,
        port_candidate=decision.port_candidate,
        recommended_next_action=decision.action,
        limitations=[
            "Trusted host execution is process containment, not a security sandbox.",
            *(
                []
                if control_doctor is not None
                else [
                    "No exact Godot control was configured; engine-specific attribution is limited."
                ]
            ),
            f"Tested only {static_result.platform} and the selected manifest phases.",
            *(
                [
                    "An intermittent post-pass shutdown crash or post-fail shutdown crash occurred "
                    "and was not reproducible on a non-crashing same-phase retry; "
                    "engine canaries did not reproduce it."
                ]
                if any(
                    finding.code == "ENGINE_INTERMITTENT_SHUTDOWN_CRASH"
                    for phase in phases
                    for finding in phase.findings
                )
                else []
            ),
            *(
                [
                    "All three same-phase attempts crashed after authenticated completion; "
                    "the phase result uses pre-crash evidence. Shutdown stability remains "
                    "unverified and confidence is capped at medium."
                ]
                if any(
                    finding.code == "ENGINE_SHUTDOWN_CRASH_RETRY_EXHAUSTED"
                    for phase in phases
                    for finding in phase.findings
                )
                else []
            ),
        ],
        reproduction={
            "command": [
                "redot-compat",
                "test",
                *_source_arguments(static_result, manifest),
                "--backend",
                "host",
                "--trusted-source",
                "--allow-unsafe-host-execution",
                "--redot",
                doctor.engine.binary_path,
                *(
                    ["--godot-control", control_doctor.engine.binary_path]
                    if control_doctor is not None
                    else []
                ),
                "--manifest",
                "__REDOT_COMPAT_MANIFEST__",
            ],
            "source_sha256": static_result.source.archive_sha256,
            "engine_sha256": doctor.engine.binary_sha256,
            "godot_control_sha256": (
                control_doctor.engine.binary_sha256 if control_doctor is not None else None
            ),
            "phase_configuration_sha256": _manifest_sha256(manifest),
            "manifest": manifest.to_harness_payload(),
        },
    )
    write_reports(result, output_path)
    return result


def _run_docker_backend(
    static_result: CompatibilityResult,
    output_path: Path,
    source_root: Path,
    manifest: PluginTestManifest,
    profile: DockerProfile,
    worker_engine_sha256: str,
    phase_timeouts: PhaseTimeouts | None = None,
    archive_limits: ArchiveLimits | None = None,
) -> CompatibilityResult:
    run_id = f"run-{uuid.uuid4().hex}"
    worker_output = output_path / "docker-worker"
    worker_output.mkdir()
    timeouts = phase_timeouts or PhaseTimeouts()
    reproduction = {
        **static_result.reproduction,
        "command": [
            "redot-compat",
            "test",
            *_source_arguments(static_result, manifest),
            "--backend",
            "docker",
            "--worker-image",
            profile.image,
            "--worker-engine-sha256",
            worker_engine_sha256.casefold(),
            "--manifest",
            "__REDOT_COMPAT_MANIFEST__",
        ],
        "manifest": manifest.to_harness_payload(),
        "phase_timeouts": timeouts.model_dump(mode="json"),
        "source_sha256": static_result.source.archive_sha256,
        "worker_image": profile.image,
        "worker_engine_sha256": worker_engine_sha256.casefold(),
        "worker_run_id": run_id,
        "phase_configuration_sha256": _manifest_sha256(manifest),
    }
    request = WorkerRequest(
        run_id=run_id,
        source_subpath=".",
        phases=manifest.phases,
        engine_sha256=worker_engine_sha256.casefold(),
        manifest=manifest,
        phase_timeouts=phase_timeouts,
        archive_limits=archive_limits,
        output_subpath="result",
    )
    request_path = worker_output / "request.json"
    request_path.write_text(
        request.model_dump_json(indent=2, exclude_unset=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    heartbeat = prepare_heartbeat(output_path / "controller-heartbeat")
    command = build_docker_command(
        profile,
        run_id=run_id,
        source=source_root,
        output=worker_output,
        request_path="/output/request.json",
        heartbeat=heartbeat,
    )
    process = run_docker_command(
        command,
        run_id=run_id,
        heartbeat=heartbeat,
        working_directory=worker_output,
        output_directory=output_path / "docker-controller-logs",
        timeout_seconds=min(
            3600.0,
            sum(_phase_timeout(phase, manifest, timeouts) for phase in manifest.phases) * 6
            + timeouts.doctor
            + 120,
        ),
        max_output_bytes=profile.max_output_bytes,
    )
    if (
        process.stdout_truncated
        or process.stderr_truncated
        or process.combined_truncated
        or process.output_quota_exceeded
    ):
        phase = PhaseResult(
            phase_name=PhaseName.IMPORT,
            engine_role=EngineRole.REDOT,
            status=PhaseStatus.FAIL,
            command=process.command,
            exit_code=process.exit_code,
            stdout_path=process.stdout_path,
            stderr_path=process.stderr_path,
            combined_log_path=process.combined_log_path,
            findings=[
                Finding(
                    code="LOG_TRUNCATED",
                    severity=FindingSeverity.ERROR,
                    category=FindingCategory.TESTER,
                    message="Docker logs or worker output exceeded the retained output limit.",
                    phase=PhaseName.IMPORT,
                    engine_role=EngineRole.REDOT,
                )
            ],
        )
        decision = classify(
            ClassificationContext(inventory=static_result.inventory, phases=[phase])
        )
        return static_result.model_copy(
            update={
                "run_id": run_id,
                "sandbox": Backend.DOCKER_LINUX.value,
                "policy": static_result.policy.model_copy(
                    update={"dynamic_testing_performed": True}
                ),
                "phases": [phase],
                "findings": phase.findings,
                "classification": decision.status,
                "confidence": decision.confidence,
                "confidence_reasons": decision.confidence_reasons,
                "port_candidate": decision.port_candidate,
                "recommended_next_action": decision.action,
                "reproduction": reproduction,
            }
        )
    result_path = worker_output / "result/result.json"
    if not result_path.is_file():
        worker_error = worker_output / "worker-error.json"
        detail = (
            read_worker_text(worker_error, root=worker_output, max_bytes=64 * 1024)[:2000]
            if worker_error.is_file()
            else "worker produced no result or structured error"
        )
        raise ConfigurationError(f"Docker worker exited {process.exit_code}: {detail}")
    worker_result = CompatibilityResult.model_validate_json(
        read_worker_text(result_path, root=worker_output, max_bytes=16 * 1024 * 1024)
    )
    if (
        worker_result.inventory.plugin_roots != static_result.inventory.plugin_roots
        or worker_result.inventory.package_kind is not static_result.inventory.package_kind
    ):
        raise ConfigurationError("host and worker package inventories do not agree")
    phases = [_translate_worker_phase(phase, worker_output) for phase in worker_result.phases]
    reproduction = {
        **worker_result.reproduction,
        **reproduction,
        "worker_input_sha256": worker_result.source.archive_sha256,
    }
    return worker_result.model_copy(
        update={
            "source": static_result.source,
            "inventory": static_result.inventory,
            "phases": phases,
            "engine_canary_phases": [
                _translate_worker_phase(phase, worker_output)
                for phase in worker_result.engine_canary_phases
            ],
            "phase_retry_attempts": [
                _translate_worker_phase(phase, worker_output)
                for phase in worker_result.phase_retry_attempts
            ],
            "findings": [finding for phase in phases for finding in phase.findings],
            "sandbox": Backend.DOCKER_LINUX.value,
            "limitations": [
                *worker_result.limitations,
                "Docker reduces exposure but does not eliminate kernel, daemon, or image risk.",
            ],
            "reproduction": reproduction,
        }
    )


def _translate_worker_phase(phase: PhaseResult, worker_output: Path) -> PhaseResult:
    def translate(value: str | None) -> str | None:
        return translate_worker_path(value, worker_output=worker_output)

    return phase.model_copy(
        update={
            "working_directory": translate(phase.working_directory),
            "stdout_path": translate(phase.stdout_path),
            "stderr_path": translate(phase.stderr_path),
            "combined_log_path": translate(phase.combined_log_path),
            "artifacts": [translate(path) or path for path in phase.artifacts],
        }
    )


def _load_manifest(
    path: Path | None, static_result: CompatibilityResult, plugin_name: str
) -> PluginTestManifest:
    if path is not None:
        resolved = path.resolve(strict=True)
        text = resolved.read_text(encoding="utf-8")
        payload = json.loads(text) if resolved.suffix.casefold() == ".json" else tomllib.loads(text)
        return PluginTestManifest.model_validate(payload)
    phases = [PhaseName.IMPORT]
    if static_result.inventory.contains_editor_plugin:
        phases.append(PhaseName.EDITOR)
    return PluginTestManifest(plugin_id=plugin_name, phases=phases)


def _prepare_fixture(project: Path, source: Path, plugin_root: str) -> None:
    shutil.copytree(_BASE_HARNESS, project, dirs_exist_ok=True)
    install_selected_addon(source, plugin_root, project)


def _prepare_engine_run(
    base_root: Path,
    source_root: Path,
    plugin_root: str,
) -> tuple[Workspace, dict[str, str]]:
    workspace = create_workspace(base_root)
    # Preserve the acquired addon's original bytes for isolated same-phase retries.
    install_selected_addon(source_root, plugin_root, workspace.source)
    _prepare_fixture(workspace.project, workspace.source, f"addons/{Path(plugin_root).name}")
    return workspace, build_isolated_environment(workspace.state)


def _source_arguments(result: CompatibilityResult, manifest: PluginTestManifest) -> list[str]:
    source = result.source
    arguments = [source.requested_url_or_path]
    if source.release_tag is not None:
        arguments.extend(["--release", source.release_tag])
        if source.release_asset_name is not None:
            arguments.extend(["--asset", source.release_asset_name])
    elif source.resolved_commit is not None:
        arguments.extend(["--ref", source.resolved_commit])
    arguments.extend(["--plugin-id", manifest.plugin_id])
    if result.policy.decision is BaselineDecision.FORCED_TEST:
        arguments.append("--force-test-baseline")
    return arguments


def _manifest_sha256(manifest: PluginTestManifest) -> str:
    payload = json.dumps(
        manifest.to_harness_payload(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _enable_editor_harness(project: Path) -> None:
    destination = project / "addons/redot_compat_harness"
    if not destination.exists():
        shutil.copytree(_EDITOR_HARNESS, destination)
    project_file = project / "project.godot"
    content = project_file.read_text(encoding="utf-8")
    section = (
        "\n[editor_plugins]\n\nenabled=PackedStringArray("
        '"res://addons/redot_compat_harness/plugin.cfg")\n'
    )
    if "[editor_plugins]" not in content:
        project_file.write_text(content.rstrip() + "\n" + section, encoding="utf-8", newline="\n")


_SHUTDOWN_CRASH_CODES = {"ENGINE_SHUTDOWN_CRASH_AFTER_PASS", "ENGINE_SHUTDOWN_CRASH_AFTER_FAIL"}


_PHASE_ARGUMENTS = {
    PhaseName.IMPORT: ["--editor"],
    PhaseName.EDITOR: ["--editor"],
    PhaseName.RUNTIME: ["--script", "runtime_probe.gd"],
}


def _phase_timeout(
    phase: PhaseName,
    manifest: PluginTestManifest,
    timeouts: PhaseTimeouts,
) -> float:
    if "timeout_seconds" in manifest.model_fields_set:
        return float(manifest.timeout_seconds)
    return float(getattr(timeouts, "import_phase" if phase is PhaseName.IMPORT else phase.value))


def _run_phase(
    binary: Path,
    workspace: Workspace,
    environment: dict[str, str],
    manifest: PluginTestManifest,
    phase: PhaseName,
    role: EngineRole,
    timeouts: PhaseTimeouts,
    *,
    canary: bool = False,
) -> PhaseResult:
    if phase in {PhaseName.IMPORT, PhaseName.EDITOR}:
        _enable_editor_harness(workspace.project)
    key = secrets.token_hex(32)
    if canary and phase is PhaseName.EDITOR:
        shutil.copytree(
            _HARNESS_ROOT / "canary_plugin", workspace.project / "addons/redot_compat_canary"
        )
    config_path = workspace.state / "harness.json"
    config_path.write_text(
        json.dumps(
            {
                "run_id": workspace.run_id,
                "plugin_id": "redot_compat_canary" if canary else manifest.plugin_id,
                "mode": "canary"
                if canary and phase is not PhaseName.IMPORT
                else "import"
                if phase is PhaseName.IMPORT
                else "activate",
                "session_key": key,
                "probes": []
                if canary
                else [probe.model_dump(mode="json") for probe in manifest.probes],
            }
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    phase_environment = {**environment, "REDOT_COMPAT_HARNESS_JSON": str(config_path)}
    try:
        return run_host_phase(
            [
                str(binary),
                "--headless",
                "--audio-driver",
                "Dummy",
                "--path",
                str(workspace.project),
                *_PHASE_ARGUMENTS[phase],
                "--quit-after",
                "1800",
            ],
            phase_name=phase,
            run_id=workspace.run_id,
            working_directory=workspace.project,
            environment=phase_environment,
            log_directory=workspace.logs / phase.value,
            timeout_seconds=_phase_timeout(phase, manifest, timeouts),
            expect_harness_events=True,
            engine_role=role,
            session_key=key,
        )
    finally:
        config_path.unlink(missing_ok=True)


def _run_selected_phases(
    binary: Path,
    workspace: Workspace,
    environment: dict[str, str],
    manifest: PluginTestManifest,
    engine_role: EngineRole,
    *,
    phase_timeouts: PhaseTimeouts | None = None,
    canary_phases: list[PhaseResult] | None = None,
    retry_attempts: list[PhaseResult] | None = None,
) -> list[PhaseResult]:
    timeouts = phase_timeouts or PhaseTimeouts()
    phases: list[PhaseResult] = []
    for phase_name in manifest.phases:
        if phase_name not in _PHASE_ARGUMENTS:
            phases.append(
                PhaseResult(
                    phase_name=phase_name,
                    engine_role=engine_role,
                    status=PhaseStatus.MISSING_CAPABILITY,
                    findings=[
                        Finding(
                            code="PHASE_NOT_IMPLEMENTED",
                            severity=FindingSeverity.WARNING,
                            category=FindingCategory.TESTER,
                            message=f"Phase {phase_name.value} is not available in this build.",
                            phase=phase_name,
                            engine_role=engine_role,
                        )
                    ],
                )
            )
            continue
        phase = _run_phase(
            binary, workspace, environment, manifest, phase_name, engine_role, timeouts
        )
        if any(
            finding.code in _SHUTDOWN_CRASH_CODES or finding.code.startswith("UNREVIEWED_")
            for finding in phase.findings
        ):
            canaries = _run_canaries(binary, workspace, manifest, phase, timeouts)
            if canary_phases is not None:
                canary_phases.extend(canaries)
            reviewed = _review_engine_baseline(phase, canaries)
            if _retryable_shutdown_crash(phase) and reviewed.status is PhaseStatus.CRASH:
                phase, attempts = _retry_shutdown_phase(
                    binary, workspace, manifest, phase, timeouts
                )
                if retry_attempts is not None:
                    retry_attempts.extend(attempts)
            else:
                phase = reviewed
        phases.append(phase)
    return phases


def _authenticated_terminal(phase: PhaseResult) -> bool:
    return (
        not phase.timed_out
        and bool(phase.sentinel_events)
        and phase.sentinel_events[-1].event in {"pass", "fail"}
        and not any(
            finding.severity is FindingSeverity.CRITICAL
            or finding.code
            in {
                "LOG_TRUNCATED",
                "HARNESS_EVENT_UNAUTHENTICATED",
                "HARNESS_PROTOCOL_ERROR",
                "HARNESS_CONFIGURATION_ERROR",
                "HARNESS_INCOMPLETE",
            }
            for finding in phase.findings
        )
    )


def _terminal_status(phase: PhaseResult) -> PhaseStatus:
    return (
        PhaseStatus.FAIL
        if phase.sentinel_events[-1].event == "fail"
        or any(
            finding.severity in {FindingSeverity.ERROR, FindingSeverity.CRITICAL}
            for finding in phase.findings
        )
        else PhaseStatus.PASS
    )


def _retryable_shutdown_crash(phase: PhaseResult) -> bool:
    return (
        phase.status is PhaseStatus.CRASH
        and _authenticated_terminal(phase)
        and any(f.code in _SHUTDOWN_CRASH_CODES for f in phase.findings)
    )


def _retry_shutdown_phase(
    binary: Path,
    workspace: Workspace,
    manifest: PluginTestManifest,
    phase: PhaseResult,
    timeouts: PhaseTimeouts,
) -> tuple[PhaseResult, list[PhaseResult]]:
    attempts = [phase]
    for _attempt in range(2):
        retry_workspace, environment = _prepare_engine_run(
            workspace.root / "retries" / phase.phase_name.value,
            workspace.source,
            f"addons/{manifest.plugin_id}",
        )
        retry = _run_phase(
            binary,
            retry_workspace,
            environment,
            manifest,
            phase.phase_name,
            phase.engine_role,
            timeouts,
        )
        attempts.append(retry)
        if (
            _authenticated_terminal(retry)
            and retry.status in {PhaseStatus.PASS, PhaseStatus.FAIL}
            and retry.exit_code is not None
            and 0 <= retry.exit_code < 0xC0000000
            and (
                retry.status is PhaseStatus.FAIL
                or (retry.exit_code == 0 and _terminal_status(retry) is PhaseStatus.PASS)
            )
        ):
            warning = Finding(
                code="ENGINE_INTERMITTENT_SHUTDOWN_CRASH",
                severity=FindingSeverity.WARNING,
                category=FindingCategory.ENGINE,
                message=(
                    "An intermittent post-terminal shutdown crash was not reproducible on a "
                    "non-crashing same-phase retry; canaries did not reproduce it. "
                    "The retry's completed phase evidence determines the result."
                ),
                phase=phase.phase_name,
                engine_role=phase.engine_role,
            )
            return retry.model_copy(update={"findings": [*retry.findings, warning]}), attempts
        if not _retryable_shutdown_crash(retry):
            # A new failure must remain decisive, including tampering or truncated evidence.
            return phase.model_copy(
                update={"findings": [*phase.findings, *retry.findings]}
            ), attempts
    findings = list(phase.findings)
    for attempt in attempts[1:]:
        findings.extend(finding for finding in attempt.findings if finding not in findings)
    findings.append(
        Finding(
            code="ENGINE_SHUTDOWN_CRASH_RETRY_EXHAUSTED",
            severity=FindingSeverity.WARNING,
            category=FindingCategory.ENGINE,
            message=(
                "All three attempts crashed after authenticated completion. Pre-crash "
                "evidence determines the phase result; shutdown stability remains unverified."
            ),
            phase=phase.phase_name,
            engine_role=phase.engine_role,
        )
    )
    status = (
        PhaseStatus.FAIL
        if any(_terminal_status(attempt) is PhaseStatus.FAIL for attempt in attempts)
        else PhaseStatus.PASS
    )
    return phase.model_copy(update={"status": status, "findings": findings}), attempts


def _run_canaries(
    binary: Path,
    workspace: Workspace,
    manifest: PluginTestManifest,
    phase: PhaseResult,
    timeouts: PhaseTimeouts,
) -> list[PhaseResult]:
    canaries: list[PhaseResult] = []
    needs_crash = any(item.code in _SHUTDOWN_CRASH_CODES for item in phase.findings)
    for _attempt in range(3 if needs_crash else 1):
        canary = create_workspace(workspace.root / "canaries" / phase.phase_name.value)
        shutil.copytree(_BASE_HARNESS, canary.project, dirs_exist_ok=True)
        result = _run_phase(
            binary,
            canary,
            build_isolated_environment(canary.state),
            manifest,
            phase.phase_name,
            phase.engine_role,
            timeouts,
            canary=True,
        )
        canaries.append(result)
        if any(item.code in _SHUTDOWN_CRASH_CODES for item in result.findings):
            break
    return canaries


def _normalize_diagnostic(text: str) -> str:
    text = strip_ansi(text)
    text = re.sub(r"run-[a-fA-F0-9-]{32,36}", "<run>", text)
    text = re.sub(r"[a-fA-F0-9]{32,64}", "<id>", text)
    text = re.sub(r"(?:[A-Za-z]:[\\/]|(?:res|user)://|/)[^\s\"'<>]+", "<path>", text)
    return re.sub(r"\d+", "#", text).strip()


def _review_engine_baseline(phase: PhaseResult, canaries: list[PhaseResult]) -> PhaseResult:
    valid = [
        item
        for item in canaries
        if item.sentinel_events
        and item.sentinel_events[-1].event == "pass"
        and not any(
            finding.code
            in {
                "HARNESS_EVENT_UNAUTHENTICATED",
                "HARNESS_PROTOCOL_ERROR",
                "LOG_TRUNCATED",
            }
            for finding in item.findings
        )
    ]
    diagnostics = {
        _normalize_diagnostic(finding.raw_log_excerpt or finding.message)
        for item in valid
        for finding in item.findings
        if finding.code.startswith("UNREVIEWED_")
    }
    baseline_crash = any(
        finding.code == "ENGINE_SHUTDOWN_CRASH_AFTER_PASS"
        for item in valid
        for finding in item.findings
    )
    findings: list[Finding] = []
    for finding in phase.findings:
        if (
            finding.code.startswith("UNREVIEWED_")
            and _normalize_diagnostic(finding.raw_log_excerpt or finding.message) in diagnostics
        ):
            finding = finding.model_copy(
                update={
                    "code": "ENGINE_BASELINE_DIAGNOSTIC",
                    "severity": FindingSeverity.INFO,
                    "message": "The same diagnostic was reproduced without the selected plugin.",
                }
            )
        elif finding.code in _SHUTDOWN_CRASH_CODES and baseline_crash:
            finding = finding.model_copy(
                update={
                    "code": "ENGINE_BASELINE_SHUTDOWN_CRASH",
                    "severity": FindingSeverity.WARNING,
                    "message": "The no-op harness reproduced the shutdown crash after completion.",
                }
            )
        findings.append(finding)
    status = phase.status
    has_error = any(
        item.severity in {FindingSeverity.ERROR, FindingSeverity.CRITICAL} for item in findings
    )
    if (
        status in {PhaseStatus.FAIL, PhaseStatus.CRASH}
        and phase.sentinel_events
        and phase.sentinel_events[-1].event in {"pass", "fail"}
    ):
        if status is PhaseStatus.CRASH:
            if baseline_crash and any(
                item.code in _SHUTDOWN_CRASH_CODES for item in phase.findings
            ):
                status = _terminal_status(phase.model_copy(update={"findings": findings}))
        elif phase.exit_code == 0 and not has_error and phase.sentinel_events[-1].event == "pass":
            status = PhaseStatus.PASS
    return phase.model_copy(update={"findings": findings, "status": status})


def _missing_backend_result(
    static_result: CompatibilityResult, selection: BackendSelection
) -> CompatibilityResult:
    phase = PhaseResult(
        phase_name=PhaseName.IMPORT,
        engine_role=EngineRole.REDOT,
        status=PhaseStatus.MISSING_CAPABILITY,
        findings=[
            Finding(
                code="NO_ELIGIBLE_BACKEND",
                severity=FindingSeverity.WARNING,
                category=FindingCategory.SECURITY,
                message=selection.reason,
                phase=PhaseName.IMPORT,
                engine_role=EngineRole.REDOT,
            )
        ],
    )
    decision = classify(ClassificationContext(inventory=static_result.inventory, phases=[phase]))
    return CompatibilityResult(
        run_id=static_result.run_id,
        source=static_result.source,
        inventory=static_result.inventory,
        policy=static_result.policy,
        platform=static_result.platform,
        sandbox=Backend.NONE.value,
        phases=[phase],
        findings=phase.findings,
        classification=decision.status,
        confidence=decision.confidence,
        confidence_reasons=decision.confidence_reasons,
        port_candidate=decision.port_candidate,
        recommended_next_action=decision.action,
        limitations=[*static_result.limitations, selection.reason],
        reproduction=static_result.reproduction,
    )
