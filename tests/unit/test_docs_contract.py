from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_core_repository_documents_exist() -> None:
    required = [
        "README.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "TODO.md",
        "DECISIONS.md",
        "BLOCKERS.md",
        "LICENSE",
        "CODE_OF_CONDUCT.md",
    ]

    assert [name for name in required if not (ROOT / name).is_file()] == []


def test_security_document_does_not_overclaim_docker() -> None:
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8").lower()

    assert "arbitrary code" in security
    assert "not a universal security boundary" in security
    assert "explicit consent" in security


def test_readme_keeps_policy_skip_distinct_from_testing() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "NO_PORT_NEEDED_BASELINE_POLICY" in readme
    assert "does not prove runtime compatibility" in readme
