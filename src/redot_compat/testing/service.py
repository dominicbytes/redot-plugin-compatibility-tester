from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
import uuid
from pathlib import Path, PurePosixPath

from redot_compat.classify import ClassificationContext, classify
from redot_compat.engines.doctor import doctor_engine
from redot_compat.errors import ConfigurationError
from redot_compat.inspect.service import inspect_source
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
from redot_compat.sandbox.worker_protocol import WorkerRequest
from redot_compat.testing.host import run_host_phase
from redot_compat.workspace import Workspace, create_workspace, install_selected_addon

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE_HARNESS = Path(__file__).resolve().parents[1] / "harness"
_HARNESS_ROOT = _PACKAGE_HARNESS if _PACKAGE_HARNESS.is_dir() else _PROJECT_ROOT / "harness"
_BASE_HARNESS = _HARNESS_ROOT / "base_project"
_EDITOR_HARNESS = _HARNESS_ROOT / "editor_plugin"


def test_source(
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
    )
    if static_result.classification in {
        CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY,
        CompatibilityStatus.INVALID_PACKAGE,
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

    doctor = doctor_engine(redot, product_hint="redot")
    workspace, environment = _prepare_engine_run(
        output_path / "runs/redot",
        source_root,
        plugin_root,
        plugin_name,
        manifest,
    )
    phases = _run_selected_phases(
        redot.resolve(strict=True),
        workspace,
        environment,
        manifest,
        EngineRole.REDOT,
    )
    control_doctor = None
    if godot_control is not None:
        control_doctor = doctor_engine(godot_control, product_hint="godot")
        if control_doctor.engine.compatibility_version != doctor.engine.compatibility_version:
            raise ConfigurationError(
                "Godot control compatibility version must exactly match the Redot target "
                f"({doctor.engine.compatibility_version}); got "
                f"{control_doctor.engine.compatibility_version}"
            )
        control_workspace, control_environment = _prepare_engine_run(
            output_path / "runs/godot-control",
            source_root,
            plugin_root,
            plugin_name,
            manifest,
        )
        phases.extend(
            _run_selected_phases(
                godot_control.resolve(strict=True),
                control_workspace,
                control_environment,
                manifest,
                EngineRole.GODOT_CONTROL,
            )
        )
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
        ],
        reproduction={
            "command": [
                "redot-compat",
                "test",
                static_result.source.requested_url_or_path,
                "--backend",
                "host",
                "--trusted-source",
                "--allow-unsafe-host-execution",
                "--force-test-baseline",
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
) -> CompatibilityResult:
    run_id = f"run-{uuid.uuid4().hex}"
    worker_output = output_path / "docker-worker"
    worker_output.mkdir()
    request = WorkerRequest(
        run_id=run_id,
        source_subpath=".",
        phases=manifest.phases,
        engine_sha256=worker_engine_sha256.casefold(),
        manifest=manifest,
        output_subpath="result",
    )
    request_path = worker_output / "request.json"
    request_path.write_text(
        request.model_dump_json(indent=2) + "\n",
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
        working_directory=_PROJECT_ROOT,
        output_directory=output_path / "docker-controller-logs",
        timeout_seconds=min(
            3600.0,
            float(manifest.timeout_seconds * len(manifest.phases) + 120),
        ),
    )
    result_path = worker_output / "result/result.json"
    if not result_path.is_file():
        worker_error = worker_output / "worker-error.json"
        detail = (
            worker_error.read_text(encoding="utf-8", errors="replace")[:2000]
            if worker_error.is_file()
            else "worker produced no result or structured error"
        )
        raise ConfigurationError(f"Docker worker exited {process.exit_code}: {detail}")
    worker_result = CompatibilityResult.model_validate_json(result_path.read_text(encoding="utf-8"))
    if (
        worker_result.inventory.plugin_roots != static_result.inventory.plugin_roots
        or worker_result.inventory.package_kind is not static_result.inventory.package_kind
    ):
        raise ConfigurationError("host and worker package inventories do not agree")
    phases = [_translate_worker_phase(phase, worker_output) for phase in worker_result.phases]
    reproduction = {
        **worker_result.reproduction,
        "command": [
            "redot-compat",
            "test",
            static_result.source.requested_url_or_path,
            "--backend",
            "docker",
            "--worker-image",
            profile.image,
            "--worker-engine-sha256",
            worker_engine_sha256.casefold(),
            "--force-test-baseline",
            "--manifest",
            "__REDOT_COMPAT_MANIFEST__",
        ],
        "source_sha256": static_result.source.archive_sha256,
        "worker_input_sha256": worker_result.source.archive_sha256,
        "worker_image": profile.image,
        "worker_engine_sha256": worker_engine_sha256.casefold(),
        "worker_run_id": run_id,
        "phase_configuration_sha256": _manifest_sha256(manifest),
    }
    return worker_result.model_copy(
        update={
            "source": static_result.source,
            "inventory": static_result.inventory,
            "phases": phases,
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
        if value is None:
            return None
        path = PurePosixPath(value)
        try:
            relative = path.relative_to("/output")
        except ValueError:
            return value
        return str(worker_output.joinpath(*relative.parts))

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
    plugin_name: str,
    manifest: PluginTestManifest,
) -> tuple[Workspace, dict[str, str]]:
    workspace = create_workspace(base_root)
    _prepare_fixture(workspace.project, source_root, plugin_root)
    environment = build_isolated_environment(workspace.state)
    environment.update(
        {
            "REDOT_COMPAT_RUN_ID": workspace.run_id,
            "REDOT_COMPAT_PLUGIN_ID": plugin_name,
        }
    )
    config_path = workspace.state / "harness.json"
    config_path.write_text(
        json.dumps(manifest.to_harness_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    environment["REDOT_COMPAT_HARNESS_JSON"] = str(config_path)
    return workspace, environment


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


def _run_selected_phases(
    binary: Path,
    workspace: Workspace,
    environment: dict[str, str],
    manifest: PluginTestManifest,
    engine_role: EngineRole,
) -> list[PhaseResult]:
    phases: list[PhaseResult] = []
    for phase_name in manifest.phases:
        if phase_name is PhaseName.IMPORT:
            phases.append(
                run_host_phase(
                    [
                        str(binary),
                        "--headless",
                        "--editor",
                        "--path",
                        str(workspace.project),
                        "--quit-after",
                        "30",
                    ],
                    phase_name=phase_name,
                    run_id=workspace.run_id,
                    working_directory=workspace.project,
                    environment=environment,
                    log_directory=workspace.logs / "import",
                    timeout_seconds=min(float(manifest.timeout_seconds), 180.0),
                    expect_harness_events=False,
                    engine_role=engine_role,
                )
            )
        elif phase_name is PhaseName.EDITOR:
            _enable_editor_harness(workspace.project)
            phases.append(
                run_host_phase(
                    [
                        str(binary),
                        "--headless",
                        "--editor",
                        "--path",
                        str(workspace.project),
                        "--quit-after",
                        "300",
                    ],
                    phase_name=phase_name,
                    run_id=workspace.run_id,
                    working_directory=workspace.project,
                    environment=environment,
                    log_directory=workspace.logs / "editor",
                    timeout_seconds=float(manifest.timeout_seconds),
                    expect_harness_events=True,
                    engine_role=engine_role,
                )
            )
        elif phase_name is PhaseName.RUNTIME:
            phases.append(
                run_host_phase(
                    [
                        str(binary),
                        "--headless",
                        "--path",
                        str(workspace.project),
                        "--script",
                        "runtime_probe.gd",
                        "--quit-after",
                        "300",
                    ],
                    phase_name=phase_name,
                    run_id=workspace.run_id,
                    working_directory=workspace.project,
                    environment=environment,
                    log_directory=workspace.logs / "runtime",
                    timeout_seconds=float(manifest.timeout_seconds),
                    expect_harness_events=True,
                    engine_role=engine_role,
                )
            )
        else:
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
    return phases


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


test_source.__test__ = False  # type: ignore[attr-defined]
