from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_gitignore_does_not_exclude_source_report_package() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "\n/reports/\n" in "\n" + ignore
    assert "\nreports/\n" not in "\n" + ignore


def test_wheel_manifest_bundles_harness() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"harness" = "redot_compat/harness"' in pyproject
