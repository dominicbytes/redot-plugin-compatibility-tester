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
        "GDSCRIPT_PARSE_ERROR",
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
