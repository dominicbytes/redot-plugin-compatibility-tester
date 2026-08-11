from __future__ import annotations

from pathlib import Path

from redot_compat.inspect.service import inspect_source


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
