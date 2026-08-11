from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from redot_compat.cli import app

ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def test_baseline_inspect_writes_authoritative_and_derived_reports(tmp_path: Path) -> None:
    fixture = ROOT / "tests/fixtures/baseline_gdscript_pass"
    before = {
        path.relative_to(fixture): path.read_bytes()
        for path in fixture.rglob("*")
        if path.is_file()
    }
    output = tmp_path / "report"

    result = runner.invoke(app, ["inspect", str(fixture), "--output", str(output), "--json"])

    assert result.exit_code == 10
    payload = json.loads(result.stdout)
    assert payload["classification"] == "NO_PORT_NEEDED_BASELINE_POLICY"
    assert payload["port_candidate"] is False
    assert payload["phases"] == []
    assert json.loads((output / "result.json").read_text(encoding="utf-8")) == payload
    assert "Policy skip" in (output / "report.md").read_text(encoding="utf-8")
    after = {
        path.relative_to(fixture): path.read_bytes()
        for path in fixture.rglob("*")
        if path.is_file()
    }
    assert after == before
