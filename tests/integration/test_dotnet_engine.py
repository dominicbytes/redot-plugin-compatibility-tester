from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from redot_compat.engines.doctor import doctor_engine
from redot_compat.runner.environment import build_isolated_environment
from redot_compat.runner.process import run_process


@pytest.mark.integration
def test_exact_redot_mono_builds_and_runs_trusted_fixture(tmp_path: Path) -> None:
    mono_value = os.environ.get("REDOT_COMPAT_MONO_BIN")
    dotnet_value = os.environ.get("REDOT_COMPAT_DOTNET_ROOT")
    if not mono_value or not dotnet_value:
        pytest.skip("exact Redot Mono and portable .NET SDK are not configured")
    mono = Path(mono_value).resolve(strict=True)
    dotnet_root = Path(dotnet_value).resolve(strict=True)
    dotnet = dotnet_root / "dotnet.exe"
    if not dotnet.is_file():
        pytest.fail(f"portable dotnet executable is missing: {dotnet}")

    fixture = Path(__file__).resolve().parents[1] / "fixtures/dotnet_minimal"
    project = tmp_path / "project"
    shutil.copytree(fixture, project)
    state = tmp_path / "state"
    environment = build_isolated_environment(state, inherited=os.environ)
    environment.update(
        {
            "DOTNET_ROOT": str(dotnet_root),
            "DOTNET_CLI_HOME": str(state / "dotnet-home"),
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "DOTNET_NOLOGO": "1",
            "DOTNET_SKIP_FIRST_TIME_EXPERIENCE": "1",
            "NUGET_PACKAGES": str(state / "nuget-packages"),
            "PATH": str(dotnet_root) + os.pathsep + environment.get("PATH", ""),
        }
    )
    local_feed = mono.parent / "GodotSharp/Tools/nupkgs"
    doctor = doctor_engine(mono, product_hint="redot")
    assert doctor.engine.is_dotnet is True
    assert doctor.engine.product_version.startswith("26.2.stable.mono.official.")

    restore = run_process(
        [
            str(dotnet),
            "restore",
            str(project / "DotnetGate.csproj"),
            "--source",
            str(local_feed),
            "--packages",
            str(state / "nuget-packages"),
        ],
        working_directory=project,
        environment=environment,
        output_directory=tmp_path / "restore-logs",
        timeout_seconds=60,
    )
    assert restore.exit_code == 0
    assert restore.timed_out is False

    build = run_process(
        [
            str(dotnet),
            "build",
            str(project / "DotnetGate.csproj"),
            "--no-restore",
            "--configuration",
            "Debug",
        ],
        working_directory=project,
        environment=environment,
        output_directory=tmp_path / "build-logs",
        timeout_seconds=60,
    )
    assert build.exit_code == 0
    assert build.timed_out is False

    engine = run_process(
        [str(mono), "--headless", "--path", str(project), "--quit-after", "120"],
        working_directory=project,
        environment=environment,
        output_directory=tmp_path / "engine-logs",
        timeout_seconds=60,
    )
    stdout = Path(engine.stdout_path).read_text(encoding="utf-8", errors="replace")
    stderr = Path(engine.stderr_path).read_text(encoding="utf-8", errors="replace")
    assert engine.exit_code == 0
    assert engine.timed_out is False
    assert "REDOT_COMPAT_DOTNET_OK" in stdout
    assert "ERROR" not in stdout + stderr
    assert "WARNING" not in stdout + stderr
