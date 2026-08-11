from __future__ import annotations

from pathlib import Path

from redot_compat.inspect.native import binary_architecture, sha256
from redot_compat.inspect.parsing import get_case_insensitive, read_ini, unquote
from redot_compat.inspect.version_evidence import (
    collect_version_evidence,
    select_effective_target,
)
from redot_compat.models import NativeLibrary, PackageKind, PluginInventory

_NATIVE_SUFFIXES = {".dll", ".so", ".dylib", ".framework"}
_CPP_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp"}


def inspect_plugin(root: Path, *, plugin_id: str | None = None) -> PluginInventory:
    root = root.resolve(strict=True)
    files = _files(root)
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
        plugin_roots = [path for path in plugin_roots if Path(path).name == plugin_id]
    plugin_ids = [Path(path).name for path in plugin_roots]

    contains_rust = any(path.name == "Cargo.toml" for path in files)
    contains_dotnet = any(path.suffix.casefold() in {".csproj", ".sln"} for path in files)
    contains_native_source = any(
        path.suffix.casefold() in _CPP_SUFFIXES or path.name in {"SConstruct", "CMakeLists.txt"}
        for path in files
    )
    contains_engine_module = any(path.name == "SCsub" for path in files) and any(
        path.name.casefold().startswith("register_types") for path in files
    )
    native_libraries = _native_libraries(root, gdextensions)
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

    evidence = collect_version_evidence(root, package_kind)
    effective_target, effective_confidence, conflicts = select_effective_target(
        evidence, package_kind
    )
    entry_scripts = []
    for path in plugin_cfgs:
        script = get_case_insensitive(read_ini(path), "plugin", "script")
        if script:
            entry_scripts.append((path.parent / script).relative_to(root).as_posix())
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
        plugin_roots=plugin_roots,
        plugin_ids=plugin_ids,
        package_kind=package_kind,
        languages=languages,
        contains_editor_plugin=bool(entry_scripts),
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


def _native_libraries(root: Path, manifests: list[Path]) -> list[NativeLibrary]:
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
            exists = destination.is_file()
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
