from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from redot_compat.inspect.baseline import apply_baseline_policy
from redot_compat.inspect.inventory import inspect_plugin
from redot_compat.inspect.parsing import get_case_insensitive, read_ini, unquote
from redot_compat.inspect.service import _acquire, inspect_source
from redot_compat.models import (
    BaselineDecision,
    CompatibilityStatus,
    Confidence,
    PackageKind,
    PluginInventory,
    VersionMeaning,
)


def write(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def plugin(root: Path, name: str = "alpha") -> None:
    write(root, f"addons/{name}/plugin.cfg", '[plugin]\nscript="plugin.gd"\n')


@pytest.mark.parametrize(
    "directory",
    [
        ".github/workflows",
        "tests",
        "test",
        "examples",
        "example",
        "demo",
        "demos",
        "samples",
        "docs",
    ],
)
def test_auxiliary_evidence_is_low(tmp_path: Path, directory: str) -> None:
    plugin(tmp_path)
    write(tmp_path, f"{directory}/project.godot", 'config/features=PackedStringArray("4.2")')
    inv = inspect_plugin(tmp_path, plugin_id="alpha")
    assert inv.effective_api_confidence is Confidence.LOW
    assert apply_baseline_policy(inv).decision is BaselineDecision.UNKNOWN


def test_root_and_selected_plugin_evidence_remain_authoritative(tmp_path: Path) -> None:
    plugin(tmp_path)
    plugin(tmp_path, "beta")
    write(tmp_path, "project.godot", 'config/features=PackedStringArray("4.5.2")')
    write(tmp_path, "addons/alpha/project.godot", 'config/features=PackedStringArray("4.5.2")')
    write(tmp_path, "addons/beta/other.csproj", '<Project Sdk="Godot.NET.Sdk/4.6"/>')
    write(tmp_path, "addons/beta/other.gdextension", '[configuration]\ncompatibility_minimum="4.6"')
    inv = inspect_plugin(tmp_path, plugin_id="alpha")
    assert inv.package_kind is PackageKind.GDSCRIPT
    assert inv.effective_api_target == "4.5.2"
    assert inv.effective_api_confidence is Confidence.HIGH
    assert len(inv.version_evidence) == 2
    assert apply_baseline_policy(inv).decision is BaselineDecision.SKIP


@pytest.mark.parametrize(
    "name,text",
    [
        ("project.godot", "config_version=4\n[application]\n"),
        ("addons/alpha/native.gdnlib", "[general]\n"),
        ("addons/alpha/native.gdns", "[gd_resource]\n"),
    ],
)
def test_godot3_requires_major_upgrade(tmp_path: Path, name: str, text: str) -> None:
    source = tmp_path / "input"
    plugin(source)
    write(source, name, text)
    result = inspect_source(str(source), tmp_path / "output", force_test_baseline=True)
    assert result.classification is CompatibilityStatus.PORT_REQUIRED_MAJOR_UPGRADE
    assert result.policy.decision is BaselineDecision.TEST_REQUIRED
    assert result.port_candidate
    assert result.recommended_next_action.code == "PORT_GODOT3_TO_4"
    assert "--force-test-baseline" not in result.reproduction["command"]


@pytest.mark.parametrize("target", ["3.0", "3.5", "2.1"])
def test_major_guard_prevents_skip(tmp_path: Path, target: str) -> None:
    inv = PluginInventory(effective_api_target=target, effective_api_confidence=Confidence.HIGH)
    assert apply_baseline_policy(inv).decision is BaselineDecision.TEST_REQUIRED
    assert apply_baseline_policy(inv, force_test=True).decision is BaselineDecision.TEST_REQUIRED


def test_godot_sdk_never_skips(tmp_path: Path) -> None:
    source = tmp_path / "input"
    plugin(source)
    write(source, "plugin.csproj", '<Project Sdk="Godot.NET.Sdk/4.4.1"/>')
    result = inspect_source(str(source), tmp_path / "output")
    assert result.policy.decision is BaselineDecision.TEST_REQUIRED
    finding = next(f for f in result.findings if f.code == "DOTNET_GODOT_SDK")
    assert "Redot.NET.Sdk/26.x" in (finding.recommendation or "")


@pytest.mark.parametrize(
    "sdk,target,confidence",
    [
        ("26.2.0", "4.5.2", Confidence.HIGH),
        ("26.3.0", "4.5.2", Confidence.HIGH),
        ("26.99.0", None, Confidence.LOW),
    ],
)
def test_redot_sdk_uses_known_lineage(
    tmp_path: Path, sdk: str, target: str | None, confidence: Confidence
) -> None:
    write(tmp_path, "plugin.csproj", f'<Project Sdk="Redot.NET.Sdk/{sdk}"/>')
    inv = inspect_plugin(tmp_path)
    assert inv.effective_api_target == target
    assert inv.effective_api_confidence is confidence
    assert inv.version_evidence[0].normalized_version == target
    assert inv.version_evidence[0].confidence is confidence


def test_gdextension_maximum_requires_rebuild_without_becoming_target(tmp_path: Path) -> None:
    source = tmp_path / "input"
    write(
        source,
        "native.gdextension",
        '[configuration]\ncompatibility_minimum="4.1"\ncompatibility_maximum="4.4"\n',
    )
    result = inspect_source(str(source), tmp_path / "output")
    assert result.inventory.effective_api_target == "4.1"
    assert not result.inventory.version_conflicts
    assert result.classification is CompatibilityStatus.PORT_REQUIRED_NATIVE_REBUILD
    assert result.confidence is Confidence.HIGH
    assert result.port_candidate
    assert any(f.code == "GDEXTENSION_MAXIMUM_BELOW_BASELINE" for f in result.findings)
    assert any(
        e.meaning is VersionMeaning.DECLARED_MAXIMUM for e in result.inventory.version_evidence
    )


@pytest.mark.parametrize("reference", ["relative", "absolute", "resource"])
def test_external_native_library_is_never_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reference: str
) -> None:
    source = tmp_path / "input"
    outside = write(tmp_path, "secret.dll", "secret")
    value = {
        "relative": "../secret.dll",
        "absolute": outside.as_posix(),
        "resource": "res://../secret.dll",
    }[reference]
    write(source, "native.gdextension", f'[libraries]\nwindows.x86_64="{value}"\n')

    def forbidden(path: Path) -> str:
        pytest.fail(f"Read outside package: {path}")

    monkeypatch.setattr("redot_compat.inspect.inventory.sha256", forbidden)
    monkeypatch.setattr("redot_compat.inspect.inventory.binary_architecture", forbidden)
    inv = inspect_plugin(source)
    assert outside.is_file()
    assert not inv.native_libraries[0].exists
    assert inv.native_libraries[0].sha256 is None
    assert inv.findings[0].code == "NATIVE_LIBRARY_OUTSIDE_PACKAGE"


@pytest.mark.parametrize(
    "script,expected",
    [
        ("plugin.gd", "addons/alpha/plugin.gd"),
        ("res://addons/alpha/plugin.gd", "addons/alpha/plugin.gd"),
        ("../../../escape.gd", None),
        ("/absolute.gd", None),
        ("C:/absolute.gd", None),
        ("", None),
    ],
)
def test_safe_entry_script_resolution(tmp_path: Path, script: str, expected: str | None) -> None:
    write(tmp_path, "addons/alpha/plugin.cfg", f'[plugin]\nscript="{script}"\n')
    inv = inspect_plugin(tmp_path)
    assert inv.contains_editor_plugin
    assert inv.entry_scripts == ([expected] if expected else [])
    if script and expected is None:
        assert inv.findings[0].code == "UNSAFE_ENTRY_SCRIPT"


def test_missing_plugin_id_is_invalid_even_with_root_project(tmp_path: Path) -> None:
    source = tmp_path / "input"
    plugin(source)
    write(source, "project.godot", 'config/features=PackedStringArray("4.5")')
    result = inspect_source(str(source), tmp_path / "output", plugin_id="missing")
    assert result.classification is CompatibilityStatus.INVALID_PACKAGE
    assert any(f.code == "PLUGIN_ID_NOT_FOUND" for f in result.findings)


@pytest.mark.parametrize(
    "value,expected",
    [
        ('"a;#b" ; comment', "a;#b"),
        ("4.5 # comment", "4.5"),
        ("4.5; comment", "4.5"),
        ("'a#;b' # comment", "a#;b"),
        ('"a\\";#b" # comment', 'a\\";#b'),
    ],
)
def test_unquote_preserves_quoted_comments(value: str, expected: str) -> None:
    assert unquote(value) == expected


def test_ini_bom_crlf_and_inline_comments(tmp_path: Path) -> None:
    path = tmp_path / "plugin.cfg"
    path.write_bytes(
        b'\xef\xbb\xbf[plugin]\r\nscript="a;#b.gd" ; trailing\r\ngodot_version=4.5 # trailing\r\n'
    )
    parser = read_ini(path)
    assert get_case_insensitive(parser, "plugin", "script") == "a;#b.gd"
    assert get_case_insensitive(parser, "plugin", "godot_version") == "4.5"


@pytest.mark.parametrize("version,forced", [("4.5", True), ("4.6", False)])
def test_reproduction_force_only_when_used(tmp_path: Path, version: str, forced: bool) -> None:
    source = tmp_path / "input"
    plugin(source)
    write(source, "project.godot", f'config/features=PackedStringArray("{version}")')
    result = inspect_source(str(source), tmp_path / "output", force_test_baseline=True)
    assert ("--force-test-baseline" in result.reproduction["command"]) is forced


@pytest.mark.parametrize(
    "host,adapter,keyword",
    [
        ("github.com", "GitHubSource", "github_token"),
        ("codeberg.org", "CodebergSource", "codeberg_token"),
    ],
)
def test_acquire_forwards_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, host: str, adapter: str, keyword: str
) -> None:
    from redot_compat.inspect import service

    factory = MagicMock()

    class FakeSource:
        def __init__(self, **kwargs: str) -> None:
            factory(**kwargs)

        acquire = MagicMock()
        close = MagicMock()

    monkeypatch.setattr(service, adapter, FakeSource)
    _acquire(
        f"https://{host}/owner/repo",
        tmp_path,
        requested_ref=None,
        release=None,
        asset_pattern=None,
        **{keyword: "token"},
    )
    factory.assert_called_once_with(token="token")
    FakeSource.close.assert_called_once()


def test_legacy_native_resource_alone_requires_port(tmp_path: Path) -> None:
    source = tmp_path / "input"
    write(source, "native.gdnlib", "[general]\n")
    result = inspect_source(str(source), tmp_path / "output")
    assert result.classification is CompatibilityStatus.PORT_REQUIRED_MAJOR_UPGRADE


def test_engine_module_recommended_action_spelling(tmp_path: Path) -> None:
    source = tmp_path / "input"
    write(source, "SCsub", "")
    write(source, "register_types.cpp", "")
    result = inspect_source(str(source), tmp_path / "output")
    assert result.recommended_next_action.code == "BUILD_CUSTOM_REDOT_ENGINE"


def test_invalid_archive_uses_current_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from redot_compat.errors import UnsafeArchiveError
    from redot_compat.inspect import service

    source = write(tmp_path, "invalid.zip", "invalid")
    monkeypatch.setattr(service, "BASELINE_VERSION", "4.5.3")
    result = service._invalid_archive_result("run-test", source, UnsafeArchiveError("unsafe"))
    assert result.policy.baseline_version == "4.5.3"


def test_inspect_source_forwards_tokens(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from redot_compat.inspect import service
    from redot_compat.sources.local import acquire_local_source

    source = tmp_path / "input"
    plugin(source)
    artifact = acquire_local_source(source, tmp_path / "artifact")
    acquire = MagicMock(return_value=artifact)
    monkeypatch.setattr(service, "_acquire", acquire)
    inspect_source(
        "https://github.com/owner/repo",
        tmp_path / "output",
        github_token="github",
        codeberg_token="codeberg",
    )
    assert acquire.call_args.kwargs["github_token"] == "github"  # noqa: S105
    assert acquire.call_args.kwargs["codeberg_token"] == "codeberg"  # noqa: S105


def test_maximum_without_minimum_is_not_an_effective_target(tmp_path: Path) -> None:
    write(tmp_path, "native.gdextension", '[configuration]\ncompatibility_maximum="4.5"\n')
    inv = inspect_plugin(tmp_path)
    assert inv.effective_api_target is None
    assert apply_baseline_policy(inv).decision is BaselineDecision.TEST_REQUIRED


def test_auxiliary_maximum_does_not_force_rebuild(tmp_path: Path) -> None:
    source = tmp_path / "input"
    write(source, "native.gdextension", '[configuration]\ncompatibility_minimum="4.5"\n')
    write(source, "demo/demo.gdextension", '[configuration]\ncompatibility_maximum="4.4"\n')
    result = inspect_source(str(source), tmp_path / "output")
    assert result.classification is not CompatibilityStatus.PORT_REQUIRED_NATIVE_REBUILD


def test_unsafe_script_finding_reaches_result_and_blocks_skip(tmp_path: Path) -> None:
    source = tmp_path / "input"
    write(source, "addons/alpha/plugin.cfg", '[plugin]\nscript="../../../outside.gd"\n')
    write(source, "project.godot", 'config/features=PackedStringArray("4.5")')
    result = inspect_source(str(source), tmp_path / "output")
    assert any(f.code == "UNSAFE_ENTRY_SCRIPT" for f in result.findings)
    assert result.policy.decision is BaselineDecision.TEST_REQUIRED


def test_multiple_roots_with_baseline_evidence_stays_inconclusive(tmp_path: Path) -> None:
    source = tmp_path / "input"
    plugin(source, "alpha")
    plugin(source, "beta")
    write(source, "project.godot", 'config/features=PackedStringArray("4.5")')
    result = inspect_source(str(source), tmp_path / "output")
    assert result.classification is CompatibilityStatus.INCONCLUSIVE
    assert result.policy.decision is BaselineDecision.TEST_REQUIRED
    assert any(f.code == "MULTIPLE_PLUGIN_ROOTS" for f in result.findings)


def test_auxiliary_godot_sdk_still_blocks_skip(tmp_path: Path) -> None:
    plugin(tmp_path)
    write(tmp_path, "project.godot", 'config/features=PackedStringArray("4.5")')
    write(tmp_path, "demo/sample.csproj", '<Project Sdk="Godot.NET.Sdk/4.5"/>')
    assert (
        apply_baseline_policy(inspect_plugin(tmp_path)).decision is BaselineDecision.TEST_REQUIRED
    )


def test_addon_named_example_keeps_direct_evidence(tmp_path: Path) -> None:
    plugin(tmp_path, "example")
    write(tmp_path, "addons/example/project.godot", 'config/features=PackedStringArray("4.5")')
    inv = inspect_plugin(tmp_path, plugin_id="example")
    assert inv.effective_api_confidence is Confidence.HIGH
    assert apply_baseline_policy(inv).decision is BaselineDecision.SKIP


def test_auxiliary_plugin_manifest_does_not_raise_confidence(tmp_path: Path) -> None:
    write(tmp_path, "docs/plugin.cfg", "[plugin]\nscript=plugin.gd")
    write(tmp_path, "docs/project.godot", 'config/features=PackedStringArray("4.5")')
    assert inspect_plugin(tmp_path).effective_api_confidence is Confidence.LOW
