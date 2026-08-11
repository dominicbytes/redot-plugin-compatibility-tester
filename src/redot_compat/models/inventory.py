from __future__ import annotations

from pydantic import Field

from redot_compat.models.base import ContractModel
from redot_compat.models.enums import (
    BaselineDecision,
    Confidence,
    PackageKind,
    VersionMeaning,
)


class VersionEvidence(ContractModel):
    source_type: str
    source_path_or_url: str
    raw_value: str
    normalized_version: str | None = None
    meaning: VersionMeaning
    confidence: Confidence
    package_applicability: list[PackageKind] = Field(default_factory=list)
    notes: str = ""


class NativeLibrary(ContractModel):
    selector: str
    path: str
    exists: bool
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    platform: str | None = None
    architecture: str | None = None
    build: str | None = None
    precision: str | None = None
    features: list[str] = Field(default_factory=list)
    entry_symbol: str | None = None


class PluginInventory(ContractModel):
    plugin_roots: list[str] = Field(default_factory=list)
    plugin_ids: list[str] = Field(default_factory=list)
    package_kind: PackageKind = PackageKind.UNKNOWN
    languages: list[str] = Field(default_factory=list)
    contains_editor_plugin: bool = False
    contains_runtime_library: bool = False
    contains_gdextension: bool = False
    contains_native_source: bool = False
    contains_native_binaries: bool = False
    contains_rust: bool = False
    contains_dotnet: bool = False
    contains_engine_module: bool = False
    native_platforms: list[str] = Field(default_factory=list)
    native_architectures: list[str] = Field(default_factory=list)
    native_libraries: list[NativeLibrary] = Field(default_factory=list)
    gdextension_manifests: list[str] = Field(default_factory=list)
    project_files: list[str] = Field(default_factory=list)
    addon_files: list[str] = Field(default_factory=list)
    entry_scripts: list[str] = Field(default_factory=list)
    candidate_demo_scenes: list[str] = Field(default_factory=list)
    version_evidence: list[VersionEvidence] = Field(default_factory=list)
    effective_api_target: str | None = None
    effective_api_confidence: Confidence = Confidence.LOW
    version_conflicts: list[str] = Field(default_factory=list)
    baseline_decision: BaselineDecision = BaselineDecision.UNKNOWN
