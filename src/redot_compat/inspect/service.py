from __future__ import annotations

import platform
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from redot_compat.errors import UnsafeArchiveError
from redot_compat.inspect.baseline import apply_baseline_policy
from redot_compat.inspect.inventory import inspect_plugin
from redot_compat.models import (
    BaselineDecision,
    CompatibilityResult,
    CompatibilityStatus,
    Confidence,
    Finding,
    FindingCategory,
    FindingSeverity,
    PackageKind,
    PluginInventory,
    PolicyResult,
    RecommendedAction,
)
from redot_compat.reports import write_reports
from redot_compat.sources.base import ResolvedArtifact
from redot_compat.sources.codeberg import CodebergSource
from redot_compat.sources.github import GitHubSource
from redot_compat.sources.http_archive import HttpArchiveSource
from redot_compat.sources.local import acquire_local_source, local_file_provenance


def inspect_source(
    source: str,
    output: Path,
    *,
    requested_ref: str | None = None,
    release: str | None = None,
    asset_pattern: str | None = None,
    plugin_id: str | None = None,
    force_test_baseline: bool = False,
) -> CompatibilityResult:
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output directory must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    run_id = f"run-{uuid.uuid4()}"
    try:
        artifact = _acquire(
            source,
            output / "workspace",
            requested_ref=requested_ref,
            release=release,
            asset_pattern=asset_pattern,
        )
    except UnsafeArchiveError as exc:
        local = Path(source)
        if not local.is_file():
            raise
        result = _invalid_archive_result(run_id, local, exc)
        write_reports(result, output)
        return result

    inventory = inspect_plugin(artifact.content_root, plugin_id=plugin_id)
    policy = apply_baseline_policy(inventory, force_test=force_test_baseline)
    inventory.baseline_decision = policy.decision
    result = _classify_static(run_id, artifact, inventory, policy, plugin_id=plugin_id)
    write_reports(result, output)
    return result


def _acquire(
    source: str,
    run_dir: Path,
    *,
    requested_ref: str | None,
    release: str | None,
    asset_pattern: str | None,
) -> ResolvedArtifact:
    local = Path(source)
    if local.exists():
        if requested_ref or release or asset_pattern:
            raise ValueError("local sources do not accept --ref, --release, or --asset")
        return acquire_local_source(local, run_dir)
    parsed = urlsplit(source)
    if parsed.scheme != "https":
        raise ValueError("source must be an existing local path or supported HTTPS repository URL")
    if parsed.hostname == "github.com":
        adapter: GitHubSource | CodebergSource | HttpArchiveSource = GitHubSource()
    elif parsed.hostname == "codeberg.org":
        adapter = CodebergSource()
    else:
        adapter = HttpArchiveSource()
    try:
        if isinstance(adapter, (GitHubSource, CodebergSource)):
            return adapter.acquire(
                source,
                run_dir,
                requested_ref=requested_ref,
                release=release,
                asset_pattern=asset_pattern,
            )
        if release or asset_pattern:
            raise ValueError("direct HTTPS archives do not accept --release or --asset")
        return adapter.acquire(source, run_dir, requested_ref=requested_ref)
    finally:
        adapter.close()


def _classify_static(
    run_id: str,
    artifact: ResolvedArtifact,
    inventory: PluginInventory,
    policy: PolicyResult,
    *,
    plugin_id: str | None,
) -> CompatibilityResult:
    findings: list[Finding] = []
    limitations = [
        "Static inspection does not prove activation, runtime, export, or platform parity."
    ]
    if not inventory.plugin_roots and inventory.package_kind is PackageKind.UNKNOWN:
        classification = CompatibilityStatus.INVALID_PACKAGE
        confidence = Confidence.HIGH
        port_candidate = False
        action = RecommendedAction(
            code="FIX_PACKAGE_LAYOUT",
            text="Provide an add-on root, project, GDExtension manifest, or explicit manifest.",
        )
        findings.append(
            Finding(
                code="NO_PLUGIN_ROOT",
                severity=FindingSeverity.ERROR,
                category=FindingCategory.LAYOUT,
                message="No usable plugin or project root was detected.",
            )
        )
    elif len(inventory.plugin_roots) > 1 and plugin_id is None:
        classification = CompatibilityStatus.INCONCLUSIVE
        confidence = Confidence.HIGH
        port_candidate = False
        action = RecommendedAction(
            code="SELECT_PLUGIN_ID",
            text="Repeat the command with --plugin-id; no root was selected silently.",
        )
        findings.append(
            Finding(
                code="MULTIPLE_PLUGIN_ROOTS",
                severity=FindingSeverity.ERROR,
                category=FindingCategory.LAYOUT,
                message="Multiple independent plugin roots require an explicit selection.",
            )
        )
    elif policy.decision is BaselineDecision.SKIP:
        classification = CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY
        confidence = inventory.effective_api_confidence
        port_candidate = False
        action = RecommendedAction(
            code="NONE_BASELINE_POLICY",
            text="No port is requested by policy; use a gated dynamic run for behavioral proof.",
        )
    elif inventory.contains_engine_module:
        classification = CompatibilityStatus.PORT_REQUIRED_ENGINE_MODULE
        confidence = Confidence.HIGH
        port_candidate = True
        action = RecommendedAction(
            code="BUILD_CUSTOM_REDOD_ENGINE",
            text="This package is an engine module and requires a custom Redot build.",
        )
    else:
        classification = CompatibilityStatus.INCONCLUSIVE
        confidence = inventory.effective_api_confidence
        port_candidate = False
        action = RecommendedAction(
            code="RUN_GATED_DYNAMIC_TEST",
            text=(
                "Static evidence requires an eligible contained engine test before a port decision."
            ),
        )
        if inventory.version_conflicts:
            findings.append(
                Finding(
                    code="VERSION_EVIDENCE_CONFLICT",
                    severity=FindingSeverity.WARNING,
                    category=FindingCategory.VERSION,
                    message=inventory.version_conflicts[0],
                )
            )
    if artifact.provider_capabilities:
        limitations.append(
            "Provider capabilities: "
            + ", ".join(f"{key}={value}" for key, value in artifact.provider_capabilities.items())
        )
    return CompatibilityResult(
        run_id=run_id,
        source=artifact.provenance,
        inventory=inventory,
        policy=policy,
        platform=_platform(),
        phases=[],
        findings=findings,
        classification=classification,
        confidence=confidence,
        confidence_reasons=[_confidence_reason(inventory)],
        port_candidate=port_candidate,
        recommended_next_action=action,
        limitations=limitations,
        reproduction={
            "command": _static_reproduction_command(artifact, plugin_id),
            "source_sha256": artifact.content_sha256,
        },
    )


def _invalid_archive_result(
    run_id: str, source: Path, error: UnsafeArchiveError
) -> CompatibilityResult:
    return CompatibilityResult(
        run_id=run_id,
        source=local_file_provenance(source),
        inventory=PluginInventory(),
        policy=PolicyResult(
            baseline_version="4.5.2",
            decision=BaselineDecision.UNKNOWN,
            reason="Unsafe or malformed input was rejected before inspection.",
        ),
        platform=_platform(),
        findings=[
            Finding(
                code="UNSAFE_ARCHIVE",
                severity=FindingSeverity.CRITICAL,
                category=FindingCategory.ARCHIVE,
                message=str(error),
            )
        ],
        classification=CompatibilityStatus.INVALID_PACKAGE,
        confidence=Confidence.HIGH,
        confidence_reasons=["The archive violated a deterministic preflight invariant."],
        port_candidate=False,
        recommended_next_action=RecommendedAction(
            code="REPACKAGE_SAFELY",
            text="Create a new archive with regular relative files inside configured limits.",
        ),
        limitations=["Rejected package content was not extracted or executed."],
    )


def _confidence_reason(inventory: PluginInventory) -> str:
    if inventory.effective_api_target:
        return (
            f"Effective API target {inventory.effective_api_target} came from "
            f"{inventory.effective_api_confidence.value}-confidence package evidence."
        )
    return "No authoritative API target was found; the result is scope-limited."


def _static_reproduction_command(artifact: ResolvedArtifact, plugin_id: str | None) -> list[str]:
    source = artifact.provenance
    command = ["redot-compat", "inspect", source.requested_url_or_path]
    if source.resolved_commit:
        command.extend(["--ref", source.resolved_commit])
    elif source.release_tag:
        command.extend(["--release", source.release_tag])
        if source.release_asset_name:
            command.extend(["--asset", source.release_asset_name])
    if plugin_id:
        command.extend(["--plugin-id", plugin_id])
    return command


def _platform() -> str:
    machine = platform.machine().lower().replace("amd64", "x86_64")
    system = platform.system().lower()
    return f"{system}-{machine}"
