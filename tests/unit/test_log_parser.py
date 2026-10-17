from __future__ import annotations

from redot_compat.logs.parser import parse_engine_log
from redot_compat.models.enums import EngineRole, PhaseName


def test_log_parser_normalizes_decisive_patterns_and_bounds_excerpts() -> None:
    findings = parse_engine_log(
        "SCRIPT ERROR: Parse Error: Identifier 'RemovedClass' not declared in the current scope.\n"
        "ERROR: Can't open dynamic library: res://addons/example/bin/lib.so\n",
        phase=PhaseName.IMPORT,
        engine_role=EngineRole.REDOT,
        excerpt_limit=80,
    )

    assert [item.code for item in findings] == [
        "API_SYMBOL_MISSING",
        "NATIVE_LIBRARY_LOAD_FAILURE",
    ]
    assert all(len(item.raw_log_excerpt or "") <= 80 for item in findings)


def test_unmatched_warning_remains_visible() -> None:
    findings = parse_engine_log(
        "WARNING: suspicious thing happened",
        phase=PhaseName.RUNTIME,
        engine_role=EngineRole.REDOT,
    )

    assert findings[0].code == "UNREVIEWED_WARNING"


def test_unmatched_error_remains_visible_and_decisive() -> None:
    findings = parse_engine_log(
        "ERROR: Failed to read an unexpected engine service.",
        phase=PhaseName.RUNTIME,
        engine_role=EngineRole.REDOT,
    )

    assert findings[0].code == "UNREVIEWED_ERROR"
    assert findings[0].severity.value == "error"


def test_redot_editor_scan_shutdown_warning_is_narrowly_reviewed() -> None:
    reviewed = parse_engine_log(
        "WARNING: Scan thread aborted...",
        phase=PhaseName.IMPORT,
        engine_role=EngineRole.REDOT,
    )
    wrong_role = parse_engine_log(
        "WARNING: Scan thread aborted...",
        phase=PhaseName.IMPORT,
        engine_role=EngineRole.GODOT_CONTROL,
    )
    wrong_phase = parse_engine_log(
        "WARNING: Scan thread aborted...",
        phase=PhaseName.RUNTIME,
        engine_role=EngineRole.REDOT,
    )

    assert reviewed[0].code == "REVIEWED_EDITOR_SCAN_SHUTDOWN"
    assert reviewed[0].severity.value == "info"
    assert wrong_role[0].code == "UNREVIEWED_WARNING"
    assert wrong_phase[0].code == "UNREVIEWED_WARNING"


def test_generic_diagnostics_are_anchored_and_ansi_is_removed() -> None:
    findings = parse_engine_log(
        "Prose about warning: and error: and editor plugin disabled\n"
        "\x1b[31mUSER ERROR: actual user failure\x1b[0m\n"
        "USER WARNING: actual user warning\nSCRIPT ERROR: runtime failure\n"
        "SCRIPT ERROR: Parse Error: Unexpected token\n",
        phase=PhaseName.EDITOR,
        engine_role=EngineRole.REDOT,
    )
    assert [item.code for item in findings] == [
        "UNREVIEWED_ERROR",
        "UNREVIEWED_WARNING",
        "UNREVIEWED_ERROR",
        "GDSCRIPT_PARSE_ERROR",
    ]
    assert all("\x1b" not in (item.raw_log_excerpt or "") for item in findings)


def test_real_activation_failures_and_shutdown_leaks() -> None:
    findings = parse_engine_log(
        "WARNING: Unable to load addon script from path: res://addons/bad/plugin.gd.\n"
        "ERROR: Disabling the addon at res://addons/bad/plugin.cfg\n"
        "WARNING: ObjectDB instances leaked at exit (run with --verbose for details).\n"
        "ERROR: 2 RID allocations of type Camera3D were leaked at exit.\n"
        "ERROR: 1 resources still in use at exit.\n"
        "Leaked instance: Node:123456789\n"
        'WARNING: 2 RIDs of type "Canvas" were leaked.\n',
        phase=PhaseName.EDITOR,
        engine_role=EngineRole.REDOT,
    )
    assert [item.code for item in findings] == [
        "EDITOR_ACTIVATION_FAILURE",
        "EDITOR_ACTIVATION_FAILURE",
        *["SHUTDOWN_RESOURCE_LEAK"] * 5,
    ]
    assert all(item.severity.value == "warning" for item in findings[2:])
