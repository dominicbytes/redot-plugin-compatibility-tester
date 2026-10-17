from __future__ import annotations

from pathlib import Path, PureWindowsPath

from redot_compat.inspect.native import binary_architecture, sha256
from redot_compat.inspect.parsing import get_case_insensitive, read_ini, unquote
from redot_compat.inspect.version_evidence import (
    collect_version_evidence,
    excluded_plugin_roots,
    select_effective_target,
)
from redot_compat.models import (
    Finding,
    FindingCategory,
    FindingSeverity,
    NativeLibrary,
    PackageKind,
    PluginInventory,
)

_NATIVE_SUFFIXES = {".dll", ".so", ".dylib", ".framework"}
_CPP_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp"}


def inspect_plugin(root: Path, *, plugin_id: str | None = None) -> PluginInventory:
    root = root.resolve(strict=True)
    excluded = excluded_plugin_roots(root, plugin_id)
    files = [
        path for path in _files(root) if not any(path.is_relative_to(parent) for parent in excluded)
    ]
    findings: list[Finding] = []
    relative_files = {path: path.relative_to(root).as_posix() for path in files}
    plugin_cfgs = [path for path in files if path.name.casefold() == "plugin.cfg"]
    gdextensions = [path for path in files if path.suffix.casefold() == ".gdextension"]
    project_files = [path for path in files if path.name.casefold() == "project.godot"]
    plugin_roots = sorted(
        {
            relative_files[path.parent / path.name].rsplit("/", 1)[0]
            if "/" in relative_files[path]
            else "."
            for path in plugin_cfgs + gdextensions
        }
    )
    if plugin_id:
        plugin_roots = [path for path in plugin_roots if (root / path).name == plugin_id]
    plugin_ids = [(root / path).name for path in plugin_roots]
    if plugin_id and not plugin_roots:
        findings.append(
            Finding(
                code="PLUGIN_ID_NOT_FOUND",
                severity=FindingSeverity.ERROR,
                category=FindingCategory.LAYOUT,
                message=f"No plugin root matches --plugin-id {plugin_id}.",
            )
        )

    contains_rust = any(path.name == "Cargo.toml" for path in files)
    contains_dotnet = any(path.suffix.casefold() in {".csproj", ".sln"} for path in files)
    contains_native_source = any(
        path.suffix.casefold() in _CPP_SUFFIXES or path.name in {"SConstruct", "CMakeLists.txt"}
        for path in files
    )
    contains_engine_module = any(path.name == "SCsub" for path in files) and any(
        path.name.casefold().startswith("register_types") for path in files
    )
    native_libraries = _native_libraries(root, gdextensions, findings)
    contains_native_binaries = any(path.suffix.casefold() in _NATIVE_SUFFIXES for path in files)
    contains_gdextension = bool(gdextensions)
    package_kind = _package_kind(
        contains_engine_module=contains_engine_module,
        contains_gdextension=contains_gdextension,
        contains_native_source=contains_native_source,
        contains_rust=contains_rust,
        contains_dotnet=contains_dotnet,
        plugin_cfgs=plugin_cfgs,
        project_files=project_files,
    )
    languages: list[str] = []
    if any(path.suffix.casefold() == ".gd" for path in files):
        languages.append("GDScript")
    if contains_native_source:
        languages.append("C++")
    if contains_rust:
        languages.append("Rust")
    if contains_dotnet or any(path.suffix.casefold() == ".cs" for path in files):
        languages.append("C#")

    evidence = collect_version_evidence(root, package_kind, plugin_id=plugin_id)
    effective_target, effective_confidence, conflicts = select_effective_target(
        evidence, package_kind
    )
    entry_scripts = []
    contains_editor_plugin = False
    for path in plugin_cfgs:
        parser = read_ini(path)
        contains_editor_plugin |= parser.has_option("plugin", "script")
        script = get_case_insensitive(parser, "plugin", "script")
        if script:
            destination = _safe_entry_script(root, path.parent, script)
            if destination is None:
                findings.append(
                    Finding(
                        code="UNSAFE_ENTRY_SCRIPT",
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.SECURITY,
                        file=relative_files[path],
                        message=f"Entry script path is absolute or escapes the package: {script}",
                    )
                )
            else:
                entry_scripts.append(destination.relative_to(root).as_posix())
    addon_files = sorted(
        relative
        for path, relative in relative_files.items()
        if any(_is_relative_to(path, root / plugin_root) for plugin_root in plugin_roots)
    )
    platforms = sorted({item.platform for item in native_libraries if item.platform is not None})
    architectures = sorted(
        {item.architecture for item in native_libraries if item.architecture is not None}
    )
    return PluginInventory(
        findings=findings,
        plugin_roots=plugin_roots,
        plugin_ids=plugin_ids,
        package_kind=package_kind,
        languages=languages,
        contains_editor_plugin=contains_editor_plugin,
        contains_runtime_library=contains_gdextension,
        contains_gdextension=contains_gdextension,
        contains_native_source=contains_native_source,
        contains_native_binaries=contains_native_binaries,
        contains_rust=contains_rust,
        contains_dotnet=contains_dotnet,
        contains_engine_module=contains_engine_module,
        native_platforms=platforms,
        native_architectures=architectures,
        native_libraries=native_libraries,
        gdextension_manifests=sorted(relative_files[path] for path in gdextensions),
        project_files=sorted(relative_files[path] for path in project_files),
        addon_files=addon_files,
        entry_scripts=sorted(entry_scripts),
        candidate_demo_scenes=sorted(
            relative_files[path] for path in files if path.suffix.casefold() == ".tscn"
        ),
        version_evidence=evidence,
        effective_api_target=effective_target,
        effective_api_confidence=effective_confidence,
        version_conflicts=conflicts,
    )


def _files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and not path.is_symlink()),
        key=lambda path: path.relative_to(root).as_posix().casefold(),
    )


def _native_libraries(
    root: Path, manifests: list[Path], findings: list[Finding]
) -> list[NativeLibrary]:
    libraries: list[NativeLibrary] = []
    for manifest in manifests:
        parser = read_ini(manifest)
        entry_symbol = get_case_insensitive(parser, "configuration", "entry_symbol")
        if not parser.has_section("libraries"):
            continue
        for selector, raw_path in parser.items("libraries"):
            resource_path = unquote(raw_path) or ""
            destination = _resource_path(root, manifest.parent, resource_path)
            platform, architecture, build, precision, features = _selector(selector)
            contained = _is_relative_to(destination, root)
            if not contained:
                findings.append(
                    Finding(
                        code="NATIVE_LIBRARY_OUTSIDE_PACKAGE",
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.SECURITY,
                        file=manifest.relative_to(root).as_posix(),
                        message=f"Native library escapes the package; not read: {resource_path}",
                    )
                )
            exists = contained and destination.is_file()
            detected_architecture = binary_architecture(destination) if exists else None
            libraries.append(
                NativeLibrary(
                    selector=selector,
                    path=(
                        destination.relative_to(root).as_posix()
                        if _is_relative_to(destination, root)
                        else resource_path
                    ),
                    exists=exists,
                    sha256=sha256(destination) if exists else None,
                    platform=platform,
                    architecture=architecture or detected_architecture,
                    build=build,
                    precision=precision,
                    features=features,
                    entry_symbol=entry_symbol,
                )
            )
    return libraries


def _safe_entry_script(root: Path, plugin_root: Path, value: str) -> Path | None:
    relative = value.removeprefix("res://")
    if Path(relative).is_absolute() or PureWindowsPath(relative).drive or relative.startswith("\\"):
        return None
    try:
        destination = _resource_path(root, plugin_root, value)
    except (OSError, ValueError):
        return None
    return destination if destination.is_relative_to(root) else None


def _resource_path(root: Path, manifest_root: Path, value: str) -> Path:
    if value.startswith("res://"):
        return (root / value.removeprefix("res://")).resolve()
    return (manifest_root / value).resolve()


def _selector(selector: str) -> tuple[str | None, str | None, str | None, str | None, list[str]]:
    parts = selector.casefold().split(".")
    platform = next(
        (item for item in parts if item in {"windows", "linux", "macos", "android", "ios", "web"}),
        None,
    )
    architecture = next(
        (item for item in parts if item in {"x86_64", "x86_32", "arm64", "arm32", "universal"}),
        None,
    )
    build = next((item for item in parts if item in {"debug", "release", "editor"}), None)
    precision = next((item for item in parts if item in {"single", "double"}), None)
    known = {value for value in (platform, architecture, build, precision) if value}
    return platform, architecture, build, precision, [item for item in parts if item not in known]


def _package_kind(
    *,
    contains_engine_module: bool,
    contains_gdextension: bool,
    contains_native_source: bool,
    contains_rust: bool,
    contains_dotnet: bool,
    plugin_cfgs: list[Path],
    project_files: list[Path],
) -> PackageKind:
    if contains_engine_module:
        return PackageKind.ENGINE_MODULE
    if contains_gdextension:
        if contains_rust:
            return PackageKind.RUST_SOURCE
        if contains_native_source:
            return PackageKind.CPP_SOURCE
        return PackageKind.GDEXTENSION_PREBUILT
    if contains_dotnet:
        return PackageKind.DOTNET
    if plugin_cfgs:
        return PackageKind.GDSCRIPT
    if project_files:
        return PackageKind.PROJECT
    return PackageKind.UNKNOWN


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
