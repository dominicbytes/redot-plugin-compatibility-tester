from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from redot_compat import cli
from redot_compat.cli import app
from redot_compat.config import ArchiveLimits, PhaseTimeouts
from redot_compat.constants import VERSION
from redot_compat.errors import ConfigurationError
from redot_compat.inspect.service import inspect_source
from redot_compat.models.batch import BatchSummary

runner = CliRunner()


def test_version_plain() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"redot-compat {VERSION}"


def test_version_json() -> None:
    result = runner.invoke(app, ["version", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"name": "redot-compat", "version": VERSION}


def test_doctor_requires_an_engine_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDOT_BIN", raising=False)

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 2
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


@pytest.mark.parametrize("command", ["inspect", "test", "batch", "report"])
def test_usage_errors_return_two(
    command: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    entry = tmp_path / "input.json"
    entry.write_text("not valid input", encoding="utf-8")
    if command in {"inspect", "test"}:
        target = "inspect_source" if command == "inspect" else "run_compatibility_test"

        def invalid(*args: object, **kwargs: object) -> None:
            raise ConfigurationError("invalid selection")

        monkeypatch.setattr(cli, target, invalid)
    result = runner.invoke(app, [command, str(entry), "--output", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_api_diff_accepts_indexes_and_prints_warnings(tmp_path: Path) -> None:
    control = tmp_path / "control.json"
    candidate = tmp_path / "candidate.json"
    control.write_text('{"symbols":{},"precision":"single"}', encoding="utf-8")
    candidate.write_text('{"symbols":{},"precision":"double"}', encoding="utf-8")
    output = tmp_path / "diff.json"
    result = runner.invoke(
        app, ["api", "diff", str(control), str(candidate), "--output", str(output)]
    )
    assert result.exit_code == 0, result.output
    assert "precision differs" in result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["warnings"]


@pytest.mark.parametrize("subcommand", ["index", "diff"])
def test_api_invalid_json_is_usage_error(subcommand: str, tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[", encoding="utf-8")
    args = ["api", subcommand, str(bad)]
    if subcommand == "diff":
        args.append(str(bad))
    result = runner.invoke(app, [*args, "--output", str(tmp_path / "out.json")])
    assert result.exit_code == 2


@pytest.mark.parametrize("command", ["inspect", "test", "batch"])
def test_cli_config_propagates_tokens_and_timeouts(
    command: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    baseline = inspect_source(str(fixture), tmp_path / "baseline")
    config = tmp_path / "config.toml"
    config.write_text(
        'github_token="private-github"\ncodeberg_token="private-codeberg"\n'
        '[paths]\noutput_root="configured"\n[timeouts]\nparse=7\n[limits]\nmax_entries=42\n',
        encoding="utf-8",
    )
    captured: dict[str, object] = {}
    paths: list[Path] = []

    def run(source: object, output: Path, **kwargs: object) -> object:
        paths.append(output)
        captured.update(kwargs)
        if command == "batch":
            return BatchSummary(complete=True, total=0, completed=0, failed=0, resumed=0)
        return baseline

    target = {"inspect": "inspect_source", "test": "run_compatibility_test", "batch": "run_batch"}[
        command
    ]
    monkeypatch.setattr(cli, target, run)
    monkeypatch.setenv("GITHUB_TOKEN", "environment-github")
    manifest = tmp_path / "batch.toml"
    manifest.write_text('[[items]]\nid="one"\nsource="plugin"\n', encoding="utf-8")
    source = str(manifest) if command == "batch" else str(fixture)
    result = runner.invoke(app, [command, source, "--config", str(config)])
    assert result.exit_code == (0 if command == "batch" else 10), result.output
    assert captured["github_token"] == "private-github"  # noqa: S105 - test credential
    assert captured["codeberg_token"] == "private-codeberg"  # noqa: S105 - test credential
    assert captured["archive_limits"] == ArchiveLimits(max_entries=42)
    assert paths[0].parent == tmp_path / "configured"
    if command == "test":
        timeouts = captured["phase_timeouts"]
        assert isinstance(timeouts, PhaseTimeouts)
        assert timeouts.parse == 7
    assert "private-github" not in result.output
    assert "private-codeberg" not in result.output


def test_cli_redacts_config_tokens_in_service_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.toml"
    config.write_text('github_token="do-not-print-this"', encoding="utf-8")

    def fail(*args: object, **kwargs: object) -> None:
        raise ValueError("token do-not-print-this rejected")

    monkeypatch.setattr(cli, "inspect_source", fail)
    result = runner.invoke(app, ["inspect", "source", "--config", str(config)])
    assert result.exit_code == 2
    assert "do-not-print-this" not in result.output
    assert "<redacted>" in result.stderr


@pytest.mark.parametrize(
    ("classification", "state", "complete", "interrupted", "expected"),
    [
        ("COMPATIBLE_UNCHANGED", "completed", True, False, 0),
        ("NO_PORT_NEEDED_BASELINE_POLICY", "resumed", True, False, 10),
        ("PORT_REQUIRED_MAJOR_UPGRADE", "completed", True, False, 20),
        ("INVALID_PACKAGE", "completed", True, False, 30),
        ("CRASHED", "completed", True, False, 40),
        (None, "failed", True, False, 50),
        (None, "pending", False, True, 40),
        ("COMPATIBLE_UNCHANGED", "completed", False, False, 40),
        ("INTERNAL_TESTER_ERROR", "completed", True, False, 50),
    ],
)
def test_batch_exit_codes_follow_item_outcomes(
    classification: str | None,
    state: str,
    complete: bool,
    interrupted: bool,
    expected: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary = BatchSummary.model_validate(
        {
            "complete": complete,
            "interrupted": interrupted,
            "total": 1,
            "completed": int(state in {"completed", "resumed"}),
            "failed": int(state == "failed"),
            "resumed": int(state == "resumed"),
            "items": [
                {
                    "id": "one",
                    "fingerprint": "a" * 64,
                    "state": state,
                    "classification": classification,
                }
            ],
        }
    )
    monkeypatch.setattr(cli, "run_batch", lambda *args, **kwargs: summary)
    manifest = tmp_path / "batch.toml"
    manifest.write_text('[[items]]\nid="one"\nsource="plugin"\n', encoding="utf-8")
    result = runner.invoke(app, ["batch", str(manifest), "--output", str(tmp_path / "out")])
    assert result.exit_code == expected, result.output


def test_batch_keyboard_interrupt_returns_inconclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "batch.toml"
    manifest.write_text('[[items]]\nid="one"\nsource="plugin"\n', encoding="utf-8")

    def interrupt(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_batch", interrupt)
    result = runner.invoke(app, ["batch", str(manifest), "--output", str(tmp_path / "out")])
    assert result.exit_code == 40
    assert "interrupted" in result.stderr


@pytest.mark.parametrize("command", ["inspect", "test", "batch"])
@pytest.mark.parametrize("section", ["limits", "archive"])
def test_custom_archive_limits_are_enforced(command: str, section: str, tmp_path: Path) -> None:
    import zipfile

    archive = tmp_path / "plugin.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("addons/example/plugin.cfg", '[plugin]\nname="Example"\n')
        stream.writestr("addons/example/plugin.gd", "@tool\nextends EditorPlugin\n")
    config = tmp_path / "config.toml"
    config.write_text(f"[{section}]\nmax_entries=1\n", encoding="utf-8")
    manifest = tmp_path / "batch.toml"
    manifest.write_text(f'[[items]]\nid="one"\nsource="{archive.as_posix()}"\n')
    output = tmp_path / "out"
    source = str(manifest) if command == "batch" else str(archive)
    result = runner.invoke(app, [command, source, "--config", str(config), "--output", str(output)])
    assert result.exit_code == 30, result.output
    report = output / "items/one/result.json" if command == "batch" else output / "result.json"
    payload = json.loads(report.read_text())
    assert payload["classification"] == "INVALID_PACKAGE"
    assert payload["findings"][0]["code"] == "UNSAFE_ARCHIVE"


@pytest.mark.parametrize("command", ["doctor", "snapshot"])
def test_engine_command_bad_parameters_are_usage_errors(
    command: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def invalid(*args: object, **kwargs: object) -> None:
        raise cli.typer.BadParameter("invalid engine selection")

    binary = tmp_path / "engine.exe"
    binary.write_bytes(b"fake")
    if command == "doctor":
        monkeypatch.setattr(cli, "doctor_engine", invalid)
        args = ["doctor", "--redot", str(binary)]
    else:
        monkeypatch.setattr(cli, "snapshot_engine", invalid)
        args = [
            "api",
            "snapshot",
            str(binary),
            "--product",
            "redot",
            "--output",
            str(tmp_path / "out"),
        ]
    result = runner.invoke(app, args)
    assert result.exit_code == 2
