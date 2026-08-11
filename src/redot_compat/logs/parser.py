from __future__ import annotations

import re

from redot_compat.models import (
    EngineRole,
    Finding,
    FindingCategory,
    FindingSeverity,
    PhaseName,
)

_PATTERNS = (
    (
        re.compile(r"(?:SCRIPT ERROR: )?Parse Error:", re.IGNORECASE),
        "GDSCRIPT_PARSE_ERROR",
        FindingSeverity.ERROR,
        FindingCategory.GDSCRIPT,
    ),
    (
        re.compile(r"(?:can't|cannot|failed to) (?:open|load) dynamic librar", re.IGNORECASE),
        "NATIVE_LIBRARY_LOAD_FAILURE",
        FindingSeverity.ERROR,
        FindingCategory.NATIVE,
    ),
    (
        re.compile(
            r"(?:identifier|member).*(?:not declared|not found|doesn't exist)", re.IGNORECASE
        ),
        "API_SYMBOL_MISSING",
        FindingSeverity.ERROR,
        FindingCategory.ENGINE,
    ),
    (
        re.compile(r"editor plugin.*(?:failed|error|disabled)", re.IGNORECASE),
        "EDITOR_ACTIVATION_FAILURE",
        FindingSeverity.ERROR,
        FindingCategory.EDITOR,
    ),
)


def parse_engine_log(
    text: str,
    *,
    phase: PhaseName,
    engine_role: EngineRole,
    excerpt_limit: int = 500,
) -> list[Finding]:
    if excerpt_limit <= 0:
        raise ValueError("excerpt_limit must be positive")
    findings: list[Finding] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if (
            stripped == "WARNING: Scan thread aborted..."
            and engine_role is EngineRole.REDOT
            and phase in {PhaseName.IMPORT, PhaseName.EDITOR}
        ):
            findings.append(
                Finding(
                    code="REVIEWED_EDITOR_SCAN_SHUTDOWN",
                    severity=FindingSeverity.INFO,
                    category=FindingCategory.ENGINE,
                    message=(
                        "Redot stopped its editor scan thread during the tester's bounded shutdown."
                    ),
                    phase=phase,
                    engine_role=engine_role,
                    raw_log_excerpt=stripped,
                )
            )
            continue
        for pattern, code, severity, category in _PATTERNS:
            if pattern.search(stripped):
                findings.append(
                    Finding(
                        code=code,
                        severity=severity,
                        category=category,
                        message=_message(code),
                        phase=phase,
                        engine_role=engine_role,
                        raw_log_excerpt=stripped[:excerpt_limit],
                    )
                )
                break
        else:
            if re.search(r"\bwarning\s*:", stripped, re.IGNORECASE):
                findings.append(
                    Finding(
                        code="UNREVIEWED_WARNING",
                        severity=FindingSeverity.WARNING,
                        category=FindingCategory.ENGINE,
                        message="The engine emitted a warning not covered by a reviewed allowlist.",
                        phase=phase,
                        engine_role=engine_role,
                        raw_log_excerpt=stripped[:excerpt_limit],
                    )
                )
            elif re.search(r"\berror\s*:", stripped, re.IGNORECASE):
                findings.append(
                    Finding(
                        code="UNREVIEWED_ERROR",
                        severity=FindingSeverity.ERROR,
                        category=FindingCategory.ENGINE,
                        message="The engine emitted an error not covered by a reviewed pattern.",
                        phase=phase,
                        engine_role=engine_role,
                        raw_log_excerpt=stripped[:excerpt_limit],
                    )
                )
    return findings


def _message(code: str) -> str:
    return {
        "GDSCRIPT_PARSE_ERROR": "GDScript parsing failed in engine context.",
        "NATIVE_LIBRARY_LOAD_FAILURE": "A selected native library could not be loaded.",
        "API_SYMBOL_MISSING": "An engine API symbol used by the package was not found.",
        "EDITOR_ACTIVATION_FAILURE": "The selected editor plugin did not activate.",
    }[code]
