from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from redot_compat.exit_codes import exit_code_for
from redot_compat.inspect.service import inspect_source
from redot_compat.models import CompatibilityStatus
from redot_compat.reports.render import write_reports
from redot_compat.reports.reproduce import (
    _command,
    _powershell_quote,
    render_bash_reproduction,
    render_powershell_reproduction,
)


def test_reports_include_hash_checking_reproduction_scripts(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    output = tmp_path / "result"

    result = inspect_source(str(fixture), output)
    powershell = (output / "reproduce.ps1").read_text(encoding="utf-8")
    bash = (output / "reproduce.sh").read_text(encoding="utf-8")

    assert result.source.archive_sha256 in powershell
    assert result.source.archive_sha256 in bash
    assert "result.json" in powershell
    assert "result.json" in bash
    assert "--output" in powershell
    assert "--output" in bash


@pytest.mark.parametrize("quote", ["'", "\u2018", "\u2019", "\u201a", "\u201b"])
def test_powershell_quotes_are_doubled(quote: str) -> None:
    value = f"before{quote}$(Write-Output hostile)`n\nafter"
    assert _powershell_quote(value) == "'" + value.replace(quote, quote * 2) + "'"


@pytest.mark.parametrize("output_args", [["--output", "old-output"], ["--output=old-output"]])
def test_provided_command_preserves_full_flags_and_replaces_output(
    output_args: list[str], tmp_path: Path
) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    result = inspect_source(str(fixture), tmp_path / "result")
    hostile = "quote'\u2018\u2019\u201a\u201b$(touch unwanted)`n\nref"
    command = [
        "redot-compat",
        "test",
        hostile,
        "--ref",
        hostile,
        "--release",
        hostile,
        "--asset",
        hostile,
        "--plugin-id",
        hostile,
        "--force-test-baseline",
    ]
    result.reproduction["command"] = [*command, *output_args]
    assert _command(result) == command
    bash = render_bash_reproduction(result)
    # Parse the command as a POSIX shell would; quoted newlines must survive.
    rendered = bash.split("set +e\n", 1)[1].split("\ncode=$?", 1)[0]
    assert shlex.split(rendered.replace("\\\n", "")) == [*command, "--output", "$output"]
    powershell = render_powershell_reproduction(result)
    assert "old-output" not in powershell
    assert powershell.count("--output") == 1
    assert _powershell_quote(hostile) in powershell


@pytest.mark.parametrize("status", list(CompatibilityStatus))
def test_scripts_use_shared_classification_exit_codes(
    status: CompatibilityStatus, tmp_path: Path
) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    result = inspect_source(str(fixture), tmp_path / "result").model_copy(
        update={"classification": status}
    )
    expected = exit_code_for(status)
    assert f"$Code -ne {expected}" in render_powershell_reproduction(result)
    assert f'"$code" -ne {expected}' in render_bash_reproduction(result)


def test_powershell_reproduction_round_trips_hostile_arguments(tmp_path: Path) -> None:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        pytest.skip("PowerShell is not installed")
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    result = inspect_source(str(fixture), tmp_path / "baseline")
    hostile = "source ' \u2018 \u2019 \u201a \u201b $(Write-Error EXPANDED) `n\nnext-line"
    stub_dir = tmp_path / "quoted ' \u2018 \u2019 \u201a \u201b $(noop) `name"
    stub_dir.mkdir()
    stub = stub_dir / "capture.py"
    stub.write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "args=sys.argv[1:]\noutput=Path(args[-1])\noutput.mkdir(parents=True)\n"
        "(output/'args.json').write_text(json.dumps(args[:-2]),encoding='utf-8')\n"
        f"(output/'result.json').write_text(json.dumps({{'source':{{'archive_sha256':{result.source.archive_sha256!r}}},'classification':'NO_PORT_NEEDED_BASELINE_POLICY'}}),encoding='utf-8')\n"
        "sys.exit(10)\n",
        encoding="utf-8",
    )
    arguments = [
        hostile,
        "--ref",
        hostile,
        "--release",
        hostile,
        "--asset",
        hostile,
        "--plugin-id",
        hostile,
        "--force-test-baseline",
    ]
    result.reproduction["command"] = [
        sys.executable,
        str(stub),
        *arguments,
        "--output",
        "old-output",
    ]
    reports = tmp_path / "reports"
    write_reports(result, reports)
    output = tmp_path / "reproduced ' \u2018 \u2019 \u201a \u201b $(noop) `output"
    completed = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(reports / "reproduce.ps1"),
            "-Output",
            str(output),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads((output / "args.json").read_text(encoding="utf-8")) == arguments
    assert not (tmp_path / "old-output").exists()
