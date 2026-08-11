from __future__ import annotations

import json
from pathlib import Path

from redot_compat.models import CompatibilityResult
from redot_compat.reports.reproduce import (
    render_bash_reproduction,
    render_powershell_reproduction,
)


def result_payload(result: CompatibilityResult) -> dict[str, object]:
    return result.model_dump(mode="json", by_alias=True, exclude_none=True)


def write_reports(result: CompatibilityResult, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    payload = result_payload(result)
    (output / "result.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "report.md").write_text(render_markdown(result), encoding="utf-8", newline="\n")
    (output / "codex_port_brief.md").write_text(
        render_codex_brief(result), encoding="utf-8", newline="\n"
    )
    (output / "reproduce.ps1").write_text(
        render_powershell_reproduction(result), encoding="utf-8", newline="\n"
    )
    (output / "reproduce.sh").write_text(
        render_bash_reproduction(result), encoding="utf-8", newline="\n"
    )
    manifest = result.reproduction.get("manifest")
    if isinstance(manifest, dict):
        (output / "reproduce-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )


def render_markdown(result: CompatibilityResult) -> str:
    policy_label = (
        "Policy skip (not a runtime compatibility test)"
        if result.classification.value == "NO_PORT_NEEDED_BASELINE_POLICY"
        else result.policy.decision.value
    )
    evidence = (
        "\n".join(
            f"- `{item.meaning.value}`: `{item.raw_value}` from `{item.source_path_or_url}` "
            f"({item.confidence.value})"
            for item in result.inventory.version_evidence
        )
        or "- No version evidence was found."
    )
    findings = (
        "\n".join(
            f"- **{item.severity.value.upper()} {item.code}:** {item.message}"
            for item in result.findings
        )
        or "- None."
    )
    limitations = "\n".join(f"- {item}" for item in result.limitations) or "- None recorded."
    phases = (
        "\n".join(
            f"- `{item.engine_role.value}/{item.phase_name.value}`: `{item.status.value}` "
            f"({item.duration_ms if item.duration_ms is not None else 'not timed'} ms)"
            for item in result.phases
        )
        or "- No dynamic phases were executed."
    )
    return f"""# Redot compatibility report

## Conclusion

- Classification: `{result.classification.value}`
- Port candidate: `{str(result.port_candidate).lower()}`
- Confidence: `{result.confidence.value}`
- Policy: {policy_label}
- Next action: `{result.recommended_next_action.code}` — {result.recommended_next_action.text}

## Source

- Canonical source: `{result.source.canonical_url}`
- Resolved commit: `{result.source.resolved_commit or "local content identity"}`
- SHA-256: `{result.source.archive_sha256}`
- Size: `{result.source.archive_size}` bytes

## Inventory

- Plugin roots: `{", ".join(result.inventory.plugin_roots) or "none"}`
- Package kind: `{result.inventory.package_kind.value}`
- Languages: `{", ".join(result.inventory.languages) or "unknown"}`
- Effective target: `{result.inventory.effective_api_target or "unknown"}`

## Version evidence

{evidence}

## Phases

{phases}

## Findings

{findings}

## Limitations

{limitations}

## Reproduction

Use `reproduce.ps1` or `reproduce.sh`; each checks the resulting source SHA-256.
"""


def render_codex_brief(result: CompatibilityResult) -> str:
    findings = (
        "\n".join(f"- {item.code}: {item.message}" for item in result.findings[:10]) or "- None"
    )
    first_failure = next(
        (
            f"{phase.engine_role.value}/{phase.phase_name.value}: {phase.status.value}"
            for phase in result.phases
            if phase.status.value not in {"pass", "not_run"}
        ),
        "none",
    )
    return f"""# Codex port brief

- Upstream: {result.source.canonical_url}
- Resolved revision: {result.source.resolved_commit or result.source.archive_sha256}
- Source SHA-256: {result.source.archive_sha256}
- Effective Godot API target: {result.inventory.effective_api_target or "unknown"}
- Redot target: 26.2 / Godot lineage 4.5.2
- Classification: {result.classification.value}
- First failing phase: {first_failure}
- Suggested first action: {result.recommended_next_action.text}

## Evidence and blockers

{findings}
"""
