from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from redot_compat.archive.hash import sha256_file
from redot_compat.engines import doctor, snapshot
from redot_compat.engines.doctor import doctor_engine
from redot_compat.engines.identity import identify_engine
from redot_compat.errors import EngineError
from redot_compat.runner.process import ProcessResult


def test_doctor_rejects_missing_binary(tmp_path: Path) -> None:
    with pytest.raises(EngineError, match="does not exist"):
        doctor_engine(tmp_path / "missing", product_hint="redot", timeout_seconds=1)


def _install_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    version: str = "26.3.stable.official.85e520394",
    header: dict[str, Any] | None = None,
    exit_code: int = 0,
    diagnostics: str = "",
    invalid_json: bool = False,
    timed_out: bool = False,
) -> Path:
    binary = tmp_path / "redot-double.exe"
    binary.write_bytes(b"engine")
    payload = {
        "header": header
        if header is not None
        else {
            "version_major": 4,
            "version_minor": 5,
            "version_patch": 2,
            "precision": "single",
            "build_configuration": "debug",
        },
        "classes": [{"name": "Node"}],
    }

    def check(command, environment, timeout_seconds, name):
        return version if name == "version" else "Usage: engine"

    def identify(*args, **kwargs):
        return identify_engine(*args, **kwargs).model_copy(update={"platform": "windows"})

    def run(command, *, working_directory, environment, output_directory, timeout_seconds):
        assert "--headless" in command
        assert "--dump-extension-api" in command
        assert command[command.index("--quit-after") + 1] == "2"
        assert "-d" not in command
        assert Path(environment["HOME"]).is_dir()
        assert timeout_seconds > 0
        (working_directory / "extension_api.json").write_text(
            "{partial" if invalid_json else json.dumps(payload), encoding="utf-8"
        )
        output_directory.mkdir()
        stdout = output_directory / "stdout.log"
        stderr = output_directory / "stderr.log"
        stdout.write_text("Dumping Extension API", encoding="utf-8")
        stderr.write_text(diagnostics, encoding="utf-8")
        return ProcessResult(
            command=command,
            working_directory=str(working_directory),
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_ms=1,
            exit_code=exit_code,
            timed_out=timed_out,
            stdout_path=str(stdout),
            stderr_path=str(stderr),
            combined_log_path=str(stderr),
            ownership="test",
        )

    monkeypatch.setattr(doctor, "_run_check", check)
    monkeypatch.setattr(doctor, "identify_engine", identify)
    monkeypatch.setattr(doctor, "run_process", run)
    monkeypatch.setattr(snapshot, "run_process", run)
    return binary


def test_doctor_uses_api_header_precision_and_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_engine(monkeypatch, tmp_path)
    report = doctor_engine(binary, product_hint="redot")
    assert report.engine.precision == "single"  # Filename says double; header wins.
    assert report.engine.compatibility_version == "4.5.2"
    assert len(report.engine.extension_api_sha256 or "") == 64
    assert report.engine.extension_api_path is None  # Temporary evidence is removed.
    check = next(check for check in report.checks if check.name == "extension_api")
    assert "build_configuration='debug'" in check.detail
    assert check.passed and not check.warning


def test_doctor_unknown_redot_line_uses_header(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_engine(monkeypatch, tmp_path, version="27.1.stable.official.x")
    assert doctor_engine(binary, product_hint="redot").engine.compatibility_version == "4.5.2"


def test_doctor_rejects_known_lineage_mismatch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = _install_engine(
        monkeypatch,
        tmp_path,
        header={
            "version_major": 4,
            "version_minor": 6,
            "version_patch": 0,
        },
    )
    with pytest.raises(EngineError, match="lineage mismatch"):
        doctor_engine(binary, product_hint="redot")


@pytest.mark.parametrize(
    "header", [{}, {"version_major": "4", "version_minor": 5, "version_patch": 2}]
)
def test_doctor_rejects_incomplete_version_header(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, header: dict[str, Any]
) -> None:
    binary = _install_engine(monkeypatch, tmp_path, header=header)
    with pytest.raises(EngineError, match="integer major/minor/patch"):
        doctor_engine(binary, product_hint="redot")


_SHUTDOWN_NOISE = (
    "ERROR: 1 RID allocations of type 'P11DummyMesh' were leaked at exit.\n"
    "WARNING: ObjectDB instances leaked at exit (run with --verbose for details).\n"
)


@pytest.mark.parametrize("exit_code", [0, 3221225477, -1073741819])
def test_doctor_and_snapshot_record_reviewed_shutdown_warnings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, exit_code: int
) -> None:
    binary = _install_engine(
        monkeypatch, tmp_path, exit_code=exit_code, diagnostics=_SHUTDOWN_NOISE
    )
    doctor_report = doctor_engine(binary, product_hint="redot")
    warnings = [check for check in doctor_report.checks if check.warning]
    assert len(warnings) == (2 if exit_code == 0 else 3)
    report = snapshot.snapshot_engine(
        binary, product_hint="redot", output_directory=tmp_path / "out"
    )
    assert report.deterministic
    assert all(len(run.warnings) == len(warnings) for run in report.runs)
    assert report.engine.extension_api_sha256 == sha256_file(Path(report.runs[0].snapshot_path))


@pytest.mark.parametrize(
    "options,match",
    [
        ({"exit_code": 1}, "exited 1"),
        ({"exit_code": 3221225477, "version": "26.2.stable.official.x"}, "exited"),
        ({"diagnostics": _SHUTDOWN_NOISE, "version": "26.2.stable.official.x"}, "diagnostics"),
        ({"diagnostics": _SHUTDOWN_NOISE + "ERROR: Failed to load resource\n"}, "Failed to load"),
        ({"exit_code": 3221225477, "invalid_json": True}, "valid UTF-8 JSON"),
        ({"timed_out": True}, "timed out"),
    ],
)
def test_doctor_still_rejects_unreviewed_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, options: dict[str, Any], match: str
) -> None:
    binary = _install_engine(monkeypatch, tmp_path, **options)
    with pytest.raises(EngineError, match=match):
        doctor_engine(binary, product_hint="redot")


@pytest.mark.parametrize(
    ("exit_code", "timed_out", "output", "error"),
    [
        (0, False, "version", None),
        (0, True, "", "timed out"),
        (1, False, "failed", "exited 1"),
        (0, False, "", "no output"),
    ],
)
def test_version_help_checks_use_bounded_process_runner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    exit_code: int,
    timed_out: bool,
    output: str,
    error: str | None,
) -> None:
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    stdout.write_text(output, encoding="utf-8")
    stderr.write_text("", encoding="utf-8")

    def run(command, **kwargs):
        assert kwargs["timeout_seconds"] == 1
        assert kwargs["max_log_bytes"] == 1024 * 1024
        assert kwargs["working_directory"].is_dir()
        return ProcessResult(
            command=command,
            working_directory=str(tmp_path),
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_ms=1,
            exit_code=exit_code,
            timed_out=timed_out,
            stdout_path=str(stdout),
            stderr_path=str(stderr),
            combined_log_path=str(stderr),
            ownership="test",
        )

    monkeypatch.setattr(doctor, "run_process", run)
    if error:
        with pytest.raises(EngineError, match=error):
            doctor._run_check(["engine", "--version"], {}, 1, "version")
    else:
        assert doctor._run_check(["engine", "--version"], {}, 1, "version") == output
