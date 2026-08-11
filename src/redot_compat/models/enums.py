from __future__ import annotations

from enum import StrEnum


class SourceKind(StrEnum):
    LOCAL_DIRECTORY = "local_directory"
    LOCAL_ARCHIVE = "local_archive"
    HTTP_ARCHIVE = "http_archive"
    GITHUB = "github"
    CODEBERG = "codeberg"
    GODOT_ASSET_LIBRARY = "godot_asset_library"
    GODOT_ASSET_STORE = "godot_asset_store"


class PackageKind(StrEnum):
    GDSCRIPT = "gdscript"
    GDEXTENSION_PREBUILT = "gdextension_prebuilt"
    CPP_SOURCE = "cpp_source"
    RUST_SOURCE = "rust_source"
    DOTNET = "dotnet"
    ENGINE_MODULE = "engine_module"
    PROJECT = "project"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class VersionMeaning(StrEnum):
    DECLARED_MINIMUM = "declared_minimum"
    DECLARED_MAXIMUM = "declared_maximum"
    NATIVE_BUILD_API = "native_build_api"
    PROJECT_FEATURE_VERSION = "project_feature_version"
    SOURCE_BINDING_VERSION = "source_binding_version"
    RELEASE_CLAIM = "release_claim"
    BRANCH_CLAIM = "branch_claim"
    INFERRED_ONLY = "inferred_only"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BaselineDecision(StrEnum):
    SKIP = "skip"
    TEST_REQUIRED = "test_required"
    FORCED_TEST = "forced_test"
    UNKNOWN = "unknown"


class PhaseName(StrEnum):
    DOCTOR = "doctor"
    IMPORT = "import"
    PARSE = "parse"
    DOTNET = "dotnet"
    EDITOR = "editor"
    RUNTIME = "runtime"
    GUI = "gui"
    EXPORT = "export"
    CONTROL = "control"


class EngineRole(StrEnum):
    REDOT = "redot"
    GODOT_CONTROL = "godot_control"
    NONE = "none"


class PhaseStatus(StrEnum):
    NOT_RUN = "not_run"
    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    CRASH = "crash"
    MISSING_CAPABILITY = "missing_capability"
    TESTER_ERROR = "tester_error"


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class FindingCategory(StrEnum):
    ARCHIVE = "archive"
    SOURCE = "source"
    LAYOUT = "layout"
    VERSION = "version"
    NATIVE = "native"
    GDSCRIPT = "gdscript"
    EDITOR = "editor"
    RUNTIME = "runtime"
    EXPORT = "export"
    ENGINE = "engine"
    PLATFORM = "platform"
    SECURITY = "security"
    TESTER = "tester"
    UPSTREAM = "upstream"


class CompatibilityStatus(StrEnum):
    NO_PORT_NEEDED_BASELINE_POLICY = "NO_PORT_NEEDED_BASELINE_POLICY"
    COMPATIBLE_UNCHANGED = "COMPATIBLE_UNCHANGED"
    COMPATIBLE_REPACKAGE_ONLY = "COMPATIBLE_REPACKAGE_ONLY"
    PORT_REQUIRED_GDSCRIPT_API = "PORT_REQUIRED_GDSCRIPT_API"
    PORT_REQUIRED_EDITOR_API = "PORT_REQUIRED_EDITOR_API"
    PORT_REQUIRED_RUNTIME_API = "PORT_REQUIRED_RUNTIME_API"
    PORT_REQUIRED_NATIVE_REBUILD = "PORT_REQUIRED_NATIVE_REBUILD"
    PORT_REQUIRED_NATIVE_SOURCE = "PORT_REQUIRED_NATIVE_SOURCE"
    PORT_REQUIRED_RUST_BINDINGS = "PORT_REQUIRED_RUST_BINDINGS"
    PORT_REQUIRED_ENGINE_MODULE = "PORT_REQUIRED_ENGINE_MODULE"
    PORT_REQUIRED_EXPORT_PACKAGING = "PORT_REQUIRED_EXPORT_PACKAGING"
    ENGINE_API_GAP = "ENGINE_API_GAP"
    INVALID_PACKAGE = "INVALID_PACKAGE"
    UPSTREAM_PACKAGE_FAILURE = "UPSTREAM_PACKAGE_FAILURE"
    MISSING_PLATFORM_BINARY = "MISSING_PLATFORM_BINARY"
    MISSING_BUILD_ARTIFACT = "MISSING_BUILD_ARTIFACT"
    MISSING_DOTNET_ENGINE = "MISSING_DOTNET_ENGINE"
    MISSING_EXTERNAL_SERVICE = "MISSING_EXTERNAL_SERVICE"
    DISPLAY_REQUIRED = "DISPLAY_REQUIRED"
    TIMEOUT = "TIMEOUT"
    CRASHED = "CRASHED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INTERNAL_TESTER_ERROR = "INTERNAL_TESTER_ERROR"
