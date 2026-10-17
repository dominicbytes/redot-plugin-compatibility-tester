from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_actions_are_pinned_and_permissions_are_read_only() -> None:
    workflows = list((ROOT / ".github/workflows").glob("*.yml"))

    assert workflows
    for path in workflows:
        content = path.read_text(encoding="utf-8")
        _assert_read_only_policy(content)
        for action in re.findall(r"uses:\s*([^\s#]+)", content):
            assert re.search(r"@[a-f0-9]{40}$", action), (path.name, action)


def _assert_read_only_policy(content: str) -> None:
    # Parse the block-style permissions/checkout fields used by these workflows.
    # Reject inline forms rather than silently overlooking their permissions.
    lines = content.splitlines()
    assert "permissions:" in lines
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("permissions:"):
            value = stripped.partition(":")[2].split("#", 1)[0].strip()
            assert value in {"", "{}", "read-all"}, line
            indent = len(line) - len(line.lstrip())
            for child in lines[index + 1 :]:
                if not child.strip() or child.lstrip().startswith("#"):
                    continue
                if len(child) - len(child.lstrip()) <= indent:
                    break
                permission = child.split("#", 1)[0].strip().partition(":")[2].strip()
                assert permission in {"read", "none"}, child
        if re.match(r"(?:- )?uses:\s*actions/checkout@", stripped):
            indent = len(line) - len(line.lstrip())
            if stripped.startswith("- "):
                indent += 2
            step_lines = []
            for child in lines[index + 1 :]:
                if child.strip() and len(child) - len(child.lstrip()) < indent:
                    break
                step_lines.append(child)
            assert " " * indent + "with:" in step_lines
            assert " " * (indent + 2) + "persist-credentials: false" in step_lines


@pytest.mark.parametrize(
    "addition",
    [
        "permissions: write-all",
        "permissions: {contents: write}",
        "permissions:\n      contents: write",
    ],
)
def test_policy_rejects_job_write_permissions(addition: str) -> None:
    with pytest.raises(AssertionError):
        _assert_read_only_policy("permissions:\n  contents: read\njobs:\n  build:\n    " + addition)


def test_policy_rejects_workflow_write_permissions_and_checkout_credentials() -> None:
    with pytest.raises(AssertionError):
        _assert_read_only_policy("permissions:\n  contents: write\n")
    for credentials in ("", "      persist-credentials: true\n"):
        with pytest.raises(AssertionError):
            _assert_read_only_policy(
                "permissions:\n  contents: read\nsteps:\n"
                "  - uses: actions/checkout@" + "a" * 40 + "\n    with:\n" + credentials
            )


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
