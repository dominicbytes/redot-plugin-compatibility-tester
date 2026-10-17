from __future__ import annotations

import json
from pathlib import Path

import pytest

from redot_compat.config import ArchiveLimits, PhaseTimeouts
from redot_compat.engines.doctor import DoctorReport
from redot_compat.errors import ConfigurationError, EngineError, WorkerOutputError
from redot_compat.inspect.service import inspect_source
from redot_compat.models import (
    BaselineDecision,
    CompatibilityResult,
    EngineRole,
    Finding,
    FindingCategory,
    FindingSeverity,
    HarnessEvent,
    PhaseName,
    PhaseResult,
    PhaseStatus,
    PluginTestManifest,
)
from redot_compat.models.enums import CompatibilityStatus
from redot_compat.testing import service
from redot_compat.testing.service import run_compatibility_test
from redot_compat.workspace import Workspace, create_workspace


def test_baseline_test_stops_at_policy_without_engine(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"

    result = run_compatibility_test(str(fixture), tmp_path / "baseline")

    assert result.classification is CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY
    assert result.phases == []


def test_dynamic_test_refuses_silent_host_fallback(tmp_path: Path) -> None:
    source = tmp_path / "source"
    addon = source / "addons/example"
    addon.mkdir(parents=True)
    (addon / "plugin.cfg").write_text(
        '[plugin]\nname="Example"\nscript="plugin.gd"\n', encoding="utf-8"
    )
    (addon / "plugin.gd").write_text("@tool\nextends EditorPlugin\n", encoding="utf-8")
    output = tmp_path / "result"

    result = run_compatibility_test(str(source), output)

    assert result.classification is CompatibilityStatus.MISSING_EXTERNAL_SERVICE
    assert result.sandbox == "none"
    assert result.policy.dynamic_testing_performed is False
    assert json.loads((output / "result.json").read_text(encoding="utf-8"))["classification"] == (
        "MISSING_EXTERNAL_SERVICE"
    )


def test_configured_digest_pinned_docker_backend_is_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "docker-source"
    addon = source / "addons/example"
    addon.mkdir(parents=True)
    (addon / "plugin.cfg").write_text(
        '[plugin]\nname="Example"\nscript="plugin.gd"\n', encoding="utf-8"
    )
    (addon / "plugin.gd").write_text("@tool\nextends EditorPlugin\n", encoding="utf-8")
    selected: list[str] = []

    monkeypatch.setattr(
        "redot_compat.testing.service.docker_daemon_available",
        lambda: (True, "test-daemon"),
    )

    def fake_worker(static_result: CompatibilityResult, *_: object) -> CompatibilityResult:
        selected.append("docker")
        return static_result.model_copy(update={"sandbox": "docker_linux"})

    monkeypatch.setattr("redot_compat.testing.service._run_docker_backend", fake_worker)
    result = run_compatibility_test(
        str(source),
        tmp_path / "docker-result",
        backend="docker",
        worker_image="example/worker@sha256:" + "a" * 64,
        worker_engine_sha256="b" * 64,
    )

    assert selected == ["docker"]
    assert result.sandbox == "docker_linux"


def test_docker_backend_requires_image_and_engine_hash_together(tmp_path: Path) -> None:
    source = tmp_path / "incomplete-source"
    addon = source / "addons/example"
    addon.mkdir(parents=True)
    (addon / "plugin.cfg").write_text('[plugin]\nname="Example"\n', encoding="utf-8")

    with pytest.raises(ConfigurationError, match="both --worker-image"):
        run_compatibility_test(
            str(source),
            tmp_path / "incomplete-result",
            backend="docker",
            worker_image="example/worker@sha256:" + "a" * 64,
        )


@pytest.mark.parametrize("explicit,expected", [(False, 7.0), (True, 120.0)])
def test_phase_timeouts_respect_manifest_explicitness(explicit: bool, expected: float) -> None:
    manifest = (
        PluginTestManifest(plugin_id="example", timeout_seconds=120)
        if explicit
        else PluginTestManifest(plugin_id="example")
    )
    assert (
        service._phase_timeout(PhaseName.IMPORT, manifest, PhaseTimeouts(import_phase=7))
        == expected
    )


def test_invalid_control_fails_before_redot_doctor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def doctor(binary: Path, *, product_hint: str, timeout_seconds: float) -> DoctorReport:
        calls.append(product_hint)
        assert timeout_seconds == 3
        raise EngineError("bad control")

    monkeypatch.setattr(service, "doctor_engine", doctor)
    with pytest.raises(EngineError, match="bad control"):
        service._doctor_engines(tmp_path / "redot", tmp_path / "godot", PhaseTimeouts(doctor=3))
    assert calls == ["godot"]


def _static(tmp_path: Path) -> CompatibilityResult:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    return inspect_source(str(fixture), tmp_path / "static", force_test_baseline=True)


def test_reproduction_pins_source_selection_and_only_actual_policy_override(tmp_path: Path) -> None:
    result = _static(tmp_path)
    manifest = PluginTestManifest(plugin_id="example")
    result.source.resolved_commit = "a" * 40
    result.policy.decision = BaselineDecision.TEST_REQUIRED
    result.policy.force_test_baseline = True
    args = service._source_arguments(result, manifest)
    assert args[args.index("--ref") + 1] == "a" * 40
    assert args[args.index("--plugin-id") + 1] == "example"
    assert "--force-test-baseline" not in args
    result.policy.decision = BaselineDecision.FORCED_TEST
    result.source.release_tag = "v2"
    result.source.release_asset_name = "plugin.zip"
    args = service._source_arguments(result, manifest)
    assert "--ref" not in args
    assert args[args.index("--release") + 1] == "v2"
    assert args[args.index("--asset") + 1] == "plugin.zip"
    assert "--force-test-baseline" in args


def test_static_major_upgrade_returns_before_backend_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _static(tmp_path)
    result.classification = CompatibilityStatus.PORT_REQUIRED_MAJOR_UPGRADE

    provided = ("github-secret", "codeberg-secret")

    def inspect(*args: object, **kwargs: object) -> CompatibilityResult:
        assert kwargs["github_token"] == provided[0]
        assert kwargs["codeberg_token"] == provided[1]
        return result

    monkeypatch.setattr(service, "inspect_source", inspect)
    monkeypatch.setattr(
        service, "select_backend", lambda *a, **k: pytest.fail("must not select backend")
    )
    actual = run_compatibility_test(
        "source", tmp_path / "major", github_token="github-secret", codeberg_token="codeberg-secret"
    )
    assert actual.classification is CompatibilityStatus.PORT_REQUIRED_MAJOR_UPGRADE
    assert not actual.phases


def _evidence(code: str, *, crash: bool = False, excerpt: str | None = None) -> PhaseResult:
    return PhaseResult(
        phase_name=PhaseName.EDITOR,
        engine_role=EngineRole.REDOT,
        status=PhaseStatus.CRASH if crash else PhaseStatus.FAIL,
        exit_code=0xC0000005 if crash else 0,
        sentinel_events=[
            HarnessEvent(schema=2, run_id="run-test", sequence=0, event="start"),
            HarnessEvent(schema=2, run_id="run-test", sequence=1, event="pass"),
        ],
        findings=[
            Finding(
                code=code,
                severity=FindingSeverity.WARNING if crash else FindingSeverity.ERROR,
                category=FindingCategory.ENGINE,
                message="diagnostic",
                raw_log_excerpt=excerpt,
            )
        ],
    )


def test_canary_normalizes_diagnostics_and_preserves_plugin_failures() -> None:
    plugin = _evidence(
        "UNREVIEWED_ERROR", excerpt='\x1b[31mERROR: Failed 123 at "C:/run-one/file.gd"\x1b[0m'
    )
    canary = _evidence("UNREVIEWED_ERROR", excerpt='ERROR: Failed 456 at "D:/run-two/file.gd"')
    reviewed = service._review_engine_baseline(plugin, [canary])
    assert reviewed.status is PhaseStatus.PASS
    assert reviewed.findings[0].code == "ENGINE_BASELINE_DIAGNOSTIC"
    assert reviewed.findings[0].severity is FindingSeverity.INFO
    plugin.findings.append(
        Finding(
            code="API_SYMBOL_MISSING",
            severity=FindingSeverity.ERROR,
            category=FindingCategory.ENGINE,
            message="Plugin-only API error",
        )
    )
    assert service._review_engine_baseline(plugin, [canary]).status is PhaseStatus.FAIL


def test_crash_is_reviewed_only_after_canary_reproduces_shutdown_crash() -> None:
    plugin = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    assert service._review_engine_baseline(plugin, []).status is PhaseStatus.CRASH
    canary = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    reviewed = service._review_engine_baseline(plugin, [canary])
    assert reviewed.status is PhaseStatus.PASS
    assert reviewed.exit_code == 0xC0000005
    assert reviewed.findings[0].code == "ENGINE_BASELINE_SHUTDOWN_CRASH"
    canary.findings.append(
        Finding(
            code="LOG_TRUNCATED",
            severity=FindingSeverity.ERROR,
            category=FindingCategory.TESTER,
            message="truncated",
        )
    )
    assert service._review_engine_baseline(plugin, [canary]).status is PhaseStatus.CRASH


def test_canary_attempts_are_bounded_and_use_bare_projects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = create_workspace(tmp_path / "work")
    phase = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    attempts: list[Path] = []

    def run(binary: Path, bare: Workspace, *args: object, **kwargs: object) -> PhaseResult:
        project = bare.project
        assert not (project / "addons/example").exists()
        assert kwargs["canary"] is True
        attempts.append(project)
        return phase.model_copy(update={"status": PhaseStatus.PASS, "findings": []})

    monkeypatch.setattr(service, "_run_phase", run)
    canaries = service._run_canaries(
        tmp_path / "engine",
        workspace,
        PluginTestManifest(plugin_id="example"),
        phase,
        PhaseTimeouts(),
    )
    assert len(canaries) == len(attempts) == 3
    assert len(set(attempts)) == 3


def test_selected_phases_write_fresh_configs_and_enable_import_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = create_workspace(tmp_path / "work")
    import shutil

    shutil.copytree(service._BASE_HARNESS, workspace.project, dirs_exist_ok=True)
    keys: list[str] = []

    def run(command: list[str], **kwargs: object) -> PhaseResult:
        config_path = Path(kwargs["environment"]["REDOT_COMPAT_HARNESS_JSON"])
        config = json.loads(config_path.read_text())
        assert "REDOT_COMPAT_RUN_ID" not in kwargs["environment"]
        assert "REDOT_COMPAT_PLUGIN_ID" not in kwargs["environment"]
        assert kwargs["session_key"] == config["session_key"]
        assert config["mode"] == (
            "import" if kwargs["phase_name"] is PhaseName.IMPORT else "activate"
        )
        assert int(command[command.index("--quit-after") + 1]) >= 2
        assert (workspace.project / "addons/redot_compat_harness/plugin.gd").is_file()
        keys.append(config["session_key"])
        config_path.unlink()
        return PhaseResult(
            phase_name=kwargs["phase_name"],
            engine_role=kwargs["engine_role"],
            status=PhaseStatus.PASS,
        )

    monkeypatch.setattr(service, "run_host_phase", run)
    phases = service._run_selected_phases(
        tmp_path / "engine",
        workspace,
        {},
        PluginTestManifest(plugin_id="example", phases=[PhaseName.IMPORT, PhaseName.EDITOR]),
        EngineRole.REDOT,
    )
    assert len(phases) == len(set(keys)) == 2
    assert not (workspace.state / "harness.json").exists()


def test_worker_phase_translation_rejects_traversal(tmp_path: Path) -> None:
    phase = PhaseResult(
        phase_name=PhaseName.EDITOR, engine_role=EngineRole.REDOT, stdout_path="/output/../escape"
    )
    with pytest.raises(WorkerOutputError):
        service._translate_worker_phase(phase, tmp_path)


def test_canary_result_field_defaults_empty(tmp_path: Path) -> None:
    result = _static(tmp_path)
    assert result.engine_canary_phases == []
    assert "engine_canary_phases" in result.model_dump()


@pytest.mark.parametrize("field", ["engine_canary_phases", "phase_retry_attempts"])
def test_policy_skip_cannot_hide_dynamic_execution(tmp_path: Path, field: str) -> None:
    from pydantic import ValidationError

    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    result = inspect_source(str(fixture), tmp_path / "skip")
    payload = result.model_dump(mode="json")
    payload[field] = [
        _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True).model_dump(mode="json")
    ]
    with pytest.raises(ValidationError, match="policy skip cannot contain dynamic phases"):
        CompatibilityResult.model_validate(payload)


def test_docker_forwards_timeouts_quota_and_uses_own_work_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    from redot_compat.runner.process import ProcessResult
    from redot_compat.sandbox.docker_linux import DockerProfile
    from redot_compat.sandbox.worker_protocol import WorkerRequest

    static = _static(tmp_path)
    output = tmp_path / "docker"
    output.mkdir()
    timeouts = PhaseTimeouts(import_phase=9, editor=11)
    limits = ArchiveLimits(max_entries=123)
    profile = DockerProfile(image="example/worker@sha256:" + "a" * 64, max_output_bytes=12345)

    def run(command: list[str], **kwargs: object) -> ProcessResult:
        assert kwargs["working_directory"] == output / "docker-worker"
        assert kwargs["max_output_bytes"] == 12345
        assert kwargs["timeout_seconds"] >= 4 * (9 + 11)
        request = WorkerRequest.model_validate_json(
            (output / "docker-worker/request.json").read_text()
        )
        assert request.phase_timeouts == timeouts
        assert request.archive_limits == limits
        assert request.manifest is not None
        assert "timeout_seconds" not in request.manifest.model_fields_set
        return ProcessResult(
            command=command,
            working_directory=str(output / "docker-worker"),
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_ms=1,
            exit_code=137,
            timed_out=False,
            stdout_path="controller.out",
            stderr_path="controller.err",
            combined_log_path="controller.log",
            ownership="docker",
            output_quota_exceeded=True,
        )

    monkeypatch.setattr(service, "run_docker_command", run)
    result = service._run_docker_backend(
        static,
        output,
        tmp_path / "static/workspace/source",
        PluginTestManifest(plugin_id="example", phases=[PhaseName.IMPORT, PhaseName.EDITOR]),
        profile,
        "b" * 64,
        timeouts,
        limits,
    )
    assert result.classification is CompatibilityStatus.INCONCLUSIVE
    assert result.recommended_next_action.code == "RAISE_LOG_LIMIT"
    assert result.findings[0].code == "LOG_TRUNCATED"


def test_worker_passes_phase_timeouts_and_uses_shared_exit_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    from redot_compat import worker
    from redot_compat.sandbox.worker_protocol import WorkerRequest

    inputs = tmp_path / "input"
    outputs = tmp_path / "output"
    inputs.mkdir()
    outputs.mkdir()
    engine = tmp_path / "engine"
    engine.write_bytes(b"fixture-engine")
    timeouts = PhaseTimeouts(import_phase=13, editor=17)
    limits = ArchiveLimits(max_entries=123)
    request = WorkerRequest(
        run_id="run-" + "a" * 32,
        source_subpath=".",
        phases=[PhaseName.IMPORT],
        engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
        manifest=PluginTestManifest(plugin_id="example"),
        phase_timeouts=timeouts,
        archive_limits=limits,
    )
    request_path = outputs / "request.json"
    request_path.write_text(request.model_dump_json(exclude_unset=True))
    result = _static(tmp_path)
    result.classification = CompatibilityStatus.PORT_REQUIRED_MAJOR_UPGRADE

    def run(source: str, output: Path, **kwargs: object) -> CompatibilityResult:
        assert kwargs["phase_timeouts"] == timeouts
        assert kwargs["archive_limits"] == limits
        manifest = PluginTestManifest.model_validate_json(kwargs["manifest_path"].read_text())
        assert "timeout_seconds" not in manifest.model_fields_set
        return result

    monkeypatch.setattr(worker, "INPUT_ROOT", inputs)
    monkeypatch.setattr(worker, "OUTPUT_ROOT", outputs)
    monkeypatch.setattr(worker, "ENGINE", engine)
    monkeypatch.setattr(worker, "start_controller_watchdog", lambda: None)
    monkeypatch.setattr(worker, "run_compatibility_test", run)
    monkeypatch.setattr(worker, "write_reports", lambda *args: None)
    monkeypatch.setattr("sys.argv", ["worker", "--request", str(request_path)])
    with pytest.raises(SystemExit) as exc:
        worker.main()
    assert exc.value.code == 20


def test_baseline_shutdown_crash_preserves_api_failure_as_fail() -> None:
    plugin = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    plugin.findings.append(
        Finding(
            code="API_SYMBOL_MISSING",
            severity=FindingSeverity.ERROR,
            category=FindingCategory.ENGINE,
            message="The plugin API is absent.",
        )
    )
    canary = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    reviewed = service._review_engine_baseline(plugin, [canary])
    assert reviewed.status is PhaseStatus.FAIL
    assert [item.code for item in reviewed.findings] == [
        "ENGINE_BASELINE_SHUTDOWN_CRASH",
        "API_SYMBOL_MISSING",
    ]


@pytest.mark.parametrize("clean_attempt", [1, 2, None])
def test_post_pass_retry_is_bounded_and_retains_raw_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_attempt: int | None
) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    workspace, environment = service._prepare_engine_run(
        tmp_path / "runs", fixture, "addons/example"
    )
    crash = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    clean = crash.model_copy(update={"status": PhaseStatus.PASS, "exit_code": 0, "findings": []})
    projects: list[Path] = []

    def run(binary: Path, attempt: Workspace, *args: object, **kwargs: object) -> PhaseResult:
        projects.append(attempt.project)
        result = clean if len(projects) - 1 == clean_attempt else crash
        return result.model_copy(update={"working_directory": str(attempt.project)})

    monkeypatch.setattr(service, "_run_phase", run)
    monkeypatch.setattr(service, "_run_canaries", lambda *args: [clean, clean, clean])
    attempts: list[PhaseResult] = []
    canaries: list[PhaseResult] = []
    phases = service._run_selected_phases(
        tmp_path / "engine",
        workspace,
        environment,
        PluginTestManifest(plugin_id="example", phases=[PhaseName.EDITOR]),
        EngineRole.REDOT,
        canary_phases=canaries,
        retry_attempts=attempts,
    )
    assert len(projects) == (3 if clean_attempt is None else clean_attempt + 1)
    assert len(set(projects)) == len(projects)
    assert len(attempts) == len(projects)
    assert len(canaries) == 3
    assert attempts[0].status is PhaseStatus.CRASH
    if clean_attempt is None:
        assert phases[0].status is PhaseStatus.PASS
        assert phases[0].findings[-1].code == "ENGINE_SHUTDOWN_CRASH_RETRY_EXHAUSTED"
    else:
        assert phases[0].status is PhaseStatus.PASS
        assert phases[0].exit_code == 0
        assert phases[0].findings[-1].code == "ENGINE_INTERMITTENT_SHUTDOWN_CRASH"
        assert phases[0].findings[-1].severity is FindingSeverity.WARNING
        assert attempts[-1].findings == []


@pytest.mark.parametrize(
    "unsafe",
    ["pre_pass", "critical", "timeout", "no_events", "LOG_TRUNCATED", "HARNESS_PROTOCOL_ERROR"],
)
def test_unsafe_crash_is_never_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unsafe: str
) -> None:
    phase = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    if unsafe == "pre_pass":
        phase.findings = []
    elif unsafe in {"critical", "LOG_TRUNCATED", "HARNESS_PROTOCOL_ERROR"}:
        phase.findings.append(
            Finding(
                code="API_SYMBOL_MISSING" if unsafe == "critical" else unsafe,
                severity=FindingSeverity.CRITICAL
                if unsafe == "critical"
                else FindingSeverity.ERROR,
                category=FindingCategory.ENGINE,
                message="plugin error",
            )
        )
    elif unsafe == "timeout":
        phase.timed_out = True
    else:
        phase.sentinel_events = []
    monkeypatch.setattr(service, "_run_phase", lambda *args: phase)
    monkeypatch.setattr(service, "_run_canaries", lambda *args: [])
    attempts: list[PhaseResult] = []
    actual = service._run_selected_phases(
        tmp_path / "engine",
        create_workspace(tmp_path / "work"),
        {},
        PluginTestManifest(plugin_id="example", phases=[PhaseName.EDITOR]),
        EngineRole.REDOT,
        retry_attempts=attempts,
    )
    assert actual[0].status is PhaseStatus.CRASH
    assert attempts == []


@pytest.mark.parametrize("unsafe", ["missing_auth", "error", "exit", "timeout", "pre_pass_crash"])
def test_retry_requires_clean_authenticated_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unsafe: str
) -> None:
    crash = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    retry = crash.model_copy(update={"status": PhaseStatus.PASS, "exit_code": 0, "findings": []})
    if unsafe == "missing_auth":
        retry.sentinel_events = []
    elif unsafe == "error":
        retry.findings = _evidence("UNREVIEWED_ERROR").findings
    elif unsafe == "exit":
        retry.exit_code = 1
    elif unsafe == "timeout":
        retry.timed_out = True
    else:
        retry = crash.model_copy(update={"sentinel_events": [], "findings": []})
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    workspace, environment = service._prepare_engine_run(
        tmp_path / "runs", fixture, "addons/example"
    )
    results = iter([crash, retry])
    monkeypatch.setattr(service, "_run_phase", lambda *args: next(results))
    monkeypatch.setattr(service, "_run_canaries", lambda *args: [])
    attempts: list[PhaseResult] = []
    actual = service._run_selected_phases(
        tmp_path / "engine",
        workspace,
        environment,
        PluginTestManifest(plugin_id="example", phases=[PhaseName.EDITOR]),
        EngineRole.REDOT,
        retry_attempts=attempts,
    )
    assert actual[0].status is PhaseStatus.CRASH
    assert len(attempts) == 2


def test_editor_canary_installs_and_selects_noop_addon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def run(command: list[str], **kwargs: object) -> PhaseResult:
        project = Path(kwargs["working_directory"])
        config = json.loads(Path(kwargs["environment"]["REDOT_COMPAT_HARNESS_JSON"]).read_text())
        assert config["mode"] == "canary"
        assert config["plugin_id"] == "redot_compat_canary"
        assert (project / "addons/redot_compat_canary/plugin.cfg").is_file()
        assert not (project / "addons/example").exists()
        script = (project / "addons/redot_compat_harness/plugin.gd").read_text()
        assert 'in ["import", "canary"]' not in script
        return _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)

    monkeypatch.setattr(service, "run_host_phase", run)
    canaries = service._run_canaries(
        tmp_path / "engine",
        create_workspace(tmp_path / "work"),
        PluginTestManifest(plugin_id="example"),
        _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True),
        PhaseTimeouts(),
    )
    assert len(canaries) == 1


def test_reproduced_baseline_crash_does_not_retry_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    phase = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    calls: list[object] = []

    def run(*args: object) -> PhaseResult:
        calls.append(args)
        return phase

    monkeypatch.setattr(service, "_run_phase", run)
    monkeypatch.setattr(service, "_run_canaries", lambda *args: [phase])
    attempts: list[PhaseResult] = []
    phases = service._run_selected_phases(
        tmp_path / "engine",
        create_workspace(tmp_path / "work"),
        {},
        PluginTestManifest(plugin_id="example", phases=[PhaseName.EDITOR]),
        EngineRole.REDOT,
        retry_attempts=attempts,
    )
    assert len(calls) == 1
    assert not attempts
    assert phases[0].status is PhaseStatus.PASS
    assert phases[0].findings[0].code == "ENGINE_BASELINE_SHUTDOWN_CRASH"


@pytest.mark.parametrize("outcome", ["pass", "error", "fail"])
@pytest.mark.parametrize("recovered", [True, False])
@pytest.mark.parametrize("role", [EngineRole.REDOT, EngineRole.GODOT_CONTROL])
def test_recovered_service_result_retains_evidence_and_limits_confidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str, recovered: bool, role: EngineRole
) -> None:
    from redot_compat.engines.doctor import DoctorCheck
    from redot_compat.models.engine import EngineIdentity

    engine = tmp_path / "engine"
    engine.touch()
    doctor = DoctorReport(
        engine=EngineIdentity(
            product_name="Redot",
            product_version="26.3",
            compatibility_version="4.5.2",
            binary_path=str(engine),
            binary_sha256="a" * 64,
            platform="windows",
            architecture="x86_64",
            version_output="26.3.stable",
        ),
        checks=[DoctorCheck(name="fixture", passed=True, detail="fixture")],
    )
    monkeypatch.setattr(service, "_doctor_engines", lambda *args: (doctor, doctor))
    terminal = "fail" if outcome == "fail" else "pass"
    crash = _evidence(f"ENGINE_SHUTDOWN_CRASH_AFTER_{terminal.upper()}", crash=True)
    crash.engine_role = role
    crash.sentinel_events[-1].event = terminal
    if outcome == "error":
        crash.findings.extend(_evidence("UNREVIEWED_ERROR").findings)
    clean = crash.model_copy(
        update={
            "status": PhaseStatus.PASS if outcome == "pass" else PhaseStatus.FAIL,
            "exit_code": 1 if outcome == "fail" else 0,
            "findings": crash.findings[1:],
        }
    )
    other = _evidence("unused").model_copy(
        update={
            "status": PhaseStatus.PASS,
            "exit_code": 0,
            "findings": [],
            "engine_role": EngineRole.GODOT_CONTROL
            if role is EngineRole.REDOT
            else EngineRole.REDOT,
        }
    )
    retried = [crash, clean] if recovered else [crash, crash, crash]
    results = iter([*retried, other] if role is EngineRole.REDOT else [other, *retried])
    monkeypatch.setattr(service, "_run_phase", lambda *args: next(results))
    monkeypatch.setattr(service, "_run_canaries", lambda *args: [other, other, other])
    manifest = tmp_path / "manifest.toml"
    manifest.write_text('plugin_id="example"\nphases=["editor"]\n')
    output = tmp_path / "result"
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    result = run_compatibility_test(
        str(fixture),
        output,
        redot=engine,
        godot_control=engine,
        manifest_path=manifest,
        backend="host",
        trusted_source=True,
        allow_unsafe_host=True,
        force_test_baseline=True,
    )
    assert result.classification is (
        CompatibilityStatus.COMPATIBLE_UNCHANGED
        if outcome == "pass"
        else CompatibilityStatus.PORT_REQUIRED_EDITOR_API
        if role is EngineRole.REDOT
        else CompatibilityStatus.INCONCLUSIVE
    )
    assert result.confidence.value == "medium"
    assert any(
        ("intermittent post-pass shutdown crash" if recovered else "Shutdown stability remains")
        in note
        for note in result.limitations
    )
    assert [p.status for p in result.phase_retry_attempts] == (
        [PhaseStatus.CRASH, clean.status] if recovered else [PhaseStatus.CRASH] * 3
    )
    assert result.phase_retry_attempts[0].exit_code == 0xC0000005
    reviewed = next(p for p in result.phases if p.engine_role is role)
    assert reviewed.exit_code == (clean.exit_code if recovered else crash.exit_code)
    assert len(result.engine_canary_phases) == 3
    stored = CompatibilityResult.model_validate_json((output / "result.json").read_text())
    assert stored.phase_retry_attempts == result.phase_retry_attempts
    assert "Plugin phase retry attempts" in (output / "report.md").read_text()


@pytest.mark.parametrize("exit_code", [0, 0xC0000005])
def test_canary_cannot_review_away_crash_without_post_pass_marker(exit_code: int) -> None:
    plugin = _evidence("UNREVIEWED_WARNING", crash=True)
    plugin.exit_code = exit_code
    canary = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    assert service._review_engine_baseline(plugin, [canary]).status is PhaseStatus.CRASH


@pytest.mark.parametrize("terminal", ["pass", "fail"])
@pytest.mark.parametrize("role", [EngineRole.REDOT, EngineRole.GODOT_CONTROL])
@pytest.mark.parametrize("clean_attempt", [1, 2, None])
@pytest.mark.parametrize("has_error", [False, True])
def test_terminal_shutdown_crash_preserves_failure_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal: str,
    role: EngineRole,
    clean_attempt: int | None,
    has_error: bool,
) -> None:
    from redot_compat.classify import ClassificationContext, classify
    from redot_compat.classify.differential import DifferentialOutcome, compare_phase_status
    from redot_compat.models import Confidence, PackageKind, PluginInventory

    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    workspace, environment = service._prepare_engine_run(
        tmp_path / "runs", fixture, "addons/example"
    )
    crash = _evidence(f"ENGINE_SHUTDOWN_CRASH_AFTER_{terminal.upper()}", crash=True)
    crash.engine_role = role
    crash.sentinel_events[-1].event = terminal
    if has_error:
        crash.findings.extend(
            _evidence("UNREVIEWED_ERROR", excerpt="ERROR: missing exact API").findings
        )
    expected_status = PhaseStatus.FAIL if has_error or terminal == "fail" else PhaseStatus.PASS
    clean = crash.model_copy(
        update={
            "status": expected_status,
            "exit_code": 1 if terminal == "fail" else 0,
            "findings": crash.findings[1:],
        }
    )
    calls: list[Path] = []

    def run(binary: Path, attempt: Workspace, *args: object, **kwargs: object) -> PhaseResult:
        calls.append(attempt.project)
        return clean if len(calls) - 1 == clean_attempt else crash

    monkeypatch.setattr(service, "_run_phase", run)
    monkeypatch.setattr(service, "_run_canaries", lambda *args: [])
    attempts: list[PhaseResult] = []
    reviewed = service._run_selected_phases(
        tmp_path / "engine",
        workspace,
        environment,
        PluginTestManifest(plugin_id="example", phases=[PhaseName.EDITOR]),
        role,
        retry_attempts=attempts,
    )[0]
    assert len(attempts) == len(set(calls)) == (3 if clean_attempt is None else clean_attempt + 1)
    assert reviewed.status is expected_status
    assert reviewed.engine_role is role
    assert reviewed.findings[-1].severity is FindingSeverity.WARNING
    assert reviewed.findings[-1].code == (
        "ENGINE_SHUTDOWN_CRASH_RETRY_EXHAUSTED"
        if clean_attempt is None
        else "ENGINE_INTERMITTENT_SHUTDOWN_CRASH"
    )
    assert any(f.code == "UNREVIEWED_ERROR" for f in reviewed.findings) is has_error
    assert reviewed.exit_code == (crash.exit_code if clean_attempt is None else clean.exit_code)
    assert all(p.status is PhaseStatus.CRASH for p in attempts[: -1 if clean_attempt else None])
    other = PhaseResult(
        phase_name=PhaseName.EDITOR,
        engine_role=EngineRole.GODOT_CONTROL if role is EngineRole.REDOT else EngineRole.REDOT,
        status=PhaseStatus.PASS,
    )
    redot, control = (reviewed, other) if role is EngineRole.REDOT else (other, reviewed)
    decision = classify(
        ClassificationContext(
            inventory=PluginInventory(package_kind=PackageKind.GDSCRIPT),
            phases=[redot, control],
            exact_control=True,
        )
    )
    assert decision.confidence is Confidence.MEDIUM
    if expected_status is PhaseStatus.FAIL and role is EngineRole.REDOT:
        assert decision.status is CompatibilityStatus.PORT_REQUIRED_EDITOR_API
        assert decision.port_candidate
        assert (
            compare_phase_status(redot.status, control.status)
            is DifferentialOutcome.REDOT_ONLY_FAILURE
        )
    elif expected_status is PhaseStatus.FAIL:
        assert decision.status is CompatibilityStatus.INCONCLUSIVE
        assert decision.action.code == "FIX_CONTROL_FIXTURE"
        assert (
            compare_phase_status(redot.status, control.status)
            is DifferentialOutcome.CONTROL_MISMATCH
        )
    else:
        assert decision.status is CompatibilityStatus.COMPATIBLE_UNCHANGED


@pytest.mark.parametrize("later_failure", ["error", "fail"])
def test_exhausted_crashes_preserve_later_pre_crash_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, later_failure: str
) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    workspace, _ = service._prepare_engine_run(tmp_path / "runs", fixture, "addons/example")
    first = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    later = first.model_copy(deep=True)
    if later_failure == "error":
        later.findings.extend(_evidence("UNREVIEWED_ERROR").findings)
    else:
        later.sentinel_events[-1].event = "fail"
        later.findings[0].code = "ENGINE_SHUTDOWN_CRASH_AFTER_FAIL"
    results = iter([later, first])
    monkeypatch.setattr(service, "_run_phase", lambda *args: next(results))
    reviewed, attempts = service._retry_shutdown_phase(
        tmp_path / "engine",
        workspace,
        PluginTestManifest(plugin_id="example"),
        first,
        PhaseTimeouts(),
    )
    assert reviewed.status is PhaseStatus.FAIL
    assert len(attempts) == 3
    assert any(f.code == "UNREVIEWED_ERROR" for f in reviewed.findings) is (
        later_failure == "error"
    )


@pytest.mark.parametrize("terminal", ["pass", "fail"])
def test_baseline_shutdown_crash_keeps_terminal_failure(terminal: str) -> None:
    plugin = _evidence(f"ENGINE_SHUTDOWN_CRASH_AFTER_{terminal.upper()}", crash=True)
    plugin.sentinel_events[-1].event = terminal
    canary = _evidence("ENGINE_SHUTDOWN_CRASH_AFTER_PASS", crash=True)
    reviewed = service._review_engine_baseline(plugin, [canary])
    assert reviewed.status is (PhaseStatus.FAIL if terminal == "fail" else PhaseStatus.PASS)
    assert reviewed.findings[0].code == "ENGINE_BASELINE_SHUTDOWN_CRASH"
