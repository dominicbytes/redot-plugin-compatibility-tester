from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_actions_are_pinned_and_permissions_are_read_only() -> None:
    workflows = list((ROOT / ".github/workflows").glob("*.yml"))

    assert workflows
    for path in workflows:
        content = path.read_text(encoding="utf-8")
        assert "contents: read" in content
        for action in re.findall(r"uses:\s*([^\s#]+)", content):
            assert re.search(r"@[a-f0-9]{40}$", action), (path.name, action)


def test_public_pr_quality_never_runs_engine_or_plugin_test() -> None:
    quality = (ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")
    integration = (ROOT / ".github/workflows/integration-redot.yml").read_text(encoding="utf-8")

    assert "pull_request:" in quality
    assert "redot-compat test" not in quality
    assert "workflow_dispatch:" in integration
    assert "pull_request:" not in integration


def test_release_workflow_is_dry_run_only() -> None:
    release = (ROOT / ".github/workflows/release-dry-run.yml").read_text(encoding="utf-8")

    assert "pypi" not in release.casefold()
    assert "gh release" not in release.casefold()
    assert "contents: write" not in release
