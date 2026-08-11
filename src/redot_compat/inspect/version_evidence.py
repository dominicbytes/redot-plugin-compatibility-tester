from __future__ import annotations

import re
from pathlib import Path

from packaging.version import InvalidVersion, Version

from redot_compat.inspect.parsing import get_case_insensitive, read_ini
from redot_compat.models import (
    Confidence,
    PackageKind,
    VersionEvidence,
    VersionMeaning,
)

_VERSION = re.compile(r"(?<!\d)(\d+\.\d+(?:\.\d+)?)(?!\d)")
_FEATURES = re.compile(r"config/features\s*=\s*PackedStringArray\((.*?)\)", re.DOTALL)
_QUOTED = re.compile(r'["\']([^"\']+)["\']')
_RUST_API = re.compile(r"api[-_]?(\d+)[-_](\d+)")
_DOTNET_SDK = re.compile(r"Godot\.NET\.Sdk/([0-9]+(?:\.[0-9]+){1,2})", re.IGNORECASE)


def collect_version_evidence(root: Path, package_kind: PackageKind) -> list[VersionEvidence]:
    evidence: list[VersionEvidence] = []
    applicability: list[PackageKind] = (
        [package_kind] if package_kind is not PackageKind.UNKNOWN else []
    )
    for project in sorted(root.rglob("project.godot")):
        text = _read_text(project)
        match = _FEATURES.search(text)
        if not match:
            continue
        for candidate in _QUOTED.findall(match.group(1)):
            normalized = normalize_version(candidate)
            if normalized:
                evidence.append(
                    VersionEvidence(
                        source_type="project_godot",
                        source_path_or_url=_relative(project, root),
                        raw_value=candidate,
                        normalized_version=normalized,
                        meaning=VersionMeaning.PROJECT_FEATURE_VERSION,
                        confidence=Confidence.HIGH,
                        package_applicability=[PackageKind.GDSCRIPT, PackageKind.PROJECT],
                        notes="Parsed from config/features; decisive for pure GDScript.",
                    )
                )
                break
    for manifest in sorted(root.rglob("*.gdextension")):
        parser = read_ini(manifest)
        candidate = get_case_insensitive(parser, "configuration", "compatibility_minimum")
        normalized = normalize_version(candidate)
        if normalized:
            evidence.append(
                VersionEvidence(
                    source_type="gdextension_manifest",
                    source_path_or_url=_relative(manifest, root),
                    raw_value=candidate or "",
                    normalized_version=normalized,
                    meaning=VersionMeaning.NATIVE_BUILD_API,
                    confidence=Confidence.HIGH,
                    package_applicability=[
                        PackageKind.GDEXTENSION_PREBUILT,
                        PackageKind.CPP_SOURCE,
                        PackageKind.RUST_SOURCE,
                    ],
                    notes="Direct compatibility_minimum from the native manifest.",
                )
            )
    for plugin_cfg in sorted(root.rglob("plugin.cfg")):
        parser = read_ini(plugin_cfg)
        candidate = get_case_insensitive(parser, "plugin", "godot_version")
        normalized = normalize_version(candidate)
        if normalized:
            evidence.append(
                VersionEvidence(
                    source_type="plugin_manifest_claim",
                    source_path_or_url=_relative(plugin_cfg, root),
                    raw_value=candidate or "",
                    normalized_version=normalized,
                    meaning=VersionMeaning.RELEASE_CLAIM,
                    confidence=Confidence.LOW,
                    package_applicability=applicability,
                    notes="Corroborating manifest claim; cannot override direct evidence.",
                )
            )
    for cargo in sorted(root.rglob("Cargo.toml")):
        text = _read_text(cargo)
        for major, minor in _RUST_API.findall(text):
            candidate = f"{major}.{minor}"
            evidence.append(
                VersionEvidence(
                    source_type="cargo_api_feature",
                    source_path_or_url=_relative(cargo, root),
                    raw_value=f"api-{major}-{minor}",
                    normalized_version=candidate,
                    meaning=VersionMeaning.SOURCE_BINDING_VERSION,
                    confidence=Confidence.HIGH,
                    package_applicability=[PackageKind.RUST_SOURCE],
                    notes="godot-rust API feature from Cargo metadata.",
                )
            )
    for project in sorted(root.rglob("*.csproj")):
        match = _DOTNET_SDK.search(_read_text(project))
        if match:
            evidence.append(
                VersionEvidence(
                    source_type="dotnet_sdk",
                    source_path_or_url=_relative(project, root),
                    raw_value=match.group(1),
                    normalized_version=normalize_version(match.group(1)),
                    meaning=VersionMeaning.SOURCE_BINDING_VERSION,
                    confidence=Confidence.HIGH,
                    package_applicability=[PackageKind.DOTNET],
                    notes="Exact Godot.NET.Sdk declaration.",
                )
            )
    return evidence


def select_effective_target(
    evidence: list[VersionEvidence], package_kind: PackageKind
) -> tuple[str | None, Confidence, list[str]]:
    applicable = [
        item
        for item in evidence
        if item.normalized_version
        and (not item.package_applicability or package_kind in item.package_applicability)
    ]
    if not applicable:
        return None, Confidence.LOW, []
    confidence_order = {Confidence.HIGH: 3, Confidence.MEDIUM: 2, Confidence.LOW: 1}
    highest = max(confidence_order[item.confidence] for item in applicable)
    strongest = [item for item in applicable if confidence_order[item.confidence] == highest]
    selected = max(strongest, key=lambda item: Version(item.normalized_version or "0"))
    versions = sorted({item.normalized_version for item in applicable if item.normalized_version})
    conflicts = []
    if len(versions) > 1:
        conflicts.append(
            "Version evidence disagrees: "
            + ", ".join(
                f"{item.source_type}={item.normalized_version} ({item.confidence.value})"
                for item in applicable
            )
        )
    return selected.normalized_version, selected.confidence, conflicts


def normalize_version(value: str | None) -> str | None:
    if not value:
        return None
    match = _VERSION.search(value.strip().lstrip("vV"))
    if not match:
        return None
    try:
        parsed = Version(match.group(1))
    except InvalidVersion:
        return None
    return parsed.public


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()
