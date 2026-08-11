from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from redot_compat.cli import app

runner = CliRunner()


def test_version_plain() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "redot-compat 0.1.0"


def test_version_json() -> None:
    result = runner.invoke(app, ["version", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"name": "redot-compat", "version": "0.1.0"}


def test_doctor_requires_an_engine_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDOT_BIN", raising=False)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 40
    assert "--redot or REDOT_BIN" in result.stderr


def test_api_index_and_diff_commands(tmp_path: Path) -> None:
    control = tmp_path / "control.json"
    candidate = tmp_path / "candidate.json"
    control.write_text('{"header":{},"classes":[{"name":"Node"}]}', encoding="utf-8")
    candidate.write_text(
        '{"header":{},"classes":[{"name":"Node"},{"name":"Sprite2D"}]}',
        encoding="utf-8",
    )
    index_path = tmp_path / "index.json"
    diff_path = tmp_path / "diff.json"

    indexed = runner.invoke(app, ["api", "index", str(control), "--output", str(index_path)])
    diffed = runner.invoke(
        app,
        ["api", "diff", str(control), str(candidate), "--output", str(diff_path)],
    )

    assert indexed.exit_code == 0
    assert json.loads(index_path.read_text(encoding="utf-8"))["symbols"]["class:Node"]
    assert diffed.exit_code == 0
    assert json.loads(diff_path.read_text(encoding="utf-8"))["added"] == ["class:Sprite2D"]


def test_test_command_honors_baseline_policy_without_engine(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    output = tmp_path / "test-output"

    result = runner.invoke(app, ["test", str(fixture), "--output", str(output), "--json"])

    assert result.exit_code == 10
    assert json.loads(result.stdout)["classification"] == "NO_PORT_NEEDED_BASELINE_POLICY"
    assert (output / "result.json").is_file()

    regenerated = tmp_path / "regenerated"
    report = runner.invoke(
        app,
        ["report", str(output / "result.json"), "--output", str(regenerated)],
    )
    assert report.exit_code == 0
    assert (regenerated / "report.md").is_file()
    assert (regenerated / "reproduce.ps1").is_file()
