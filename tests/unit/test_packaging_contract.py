from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

import redot_compat

ROOT = Path(__file__).resolve().parents[2]


def test_gitignore_does_not_exclude_source_report_package() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "\n/reports/\n" in "\n" + ignore
    assert "\nreports/\n" not in "\n" + ignore


def test_wheel_manifest_bundles_harness() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"harness" = "redot_compat/harness"' in pyproject


def test_sdist_excludes_large_reference_artifacts() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    excluded = project["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"]

    assert "/docs/gamedev/references/*.json" in excluded
    assert "/docs/gamedev/source-of-truth.xlsx" in excluded
    assert project["project"]["version"] == "0.1.0"


def test_package_version_matches_distribution_metadata() -> None:
    assert redot_compat.__version__ == importlib.metadata.version(
        "redot-plugin-compatibility-tester"
    )
