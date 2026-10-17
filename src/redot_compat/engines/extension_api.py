from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from redot_compat.engines.lineage import redot_release_line
from redot_compat.errors import EngineError
from redot_compat.models.engine import EngineIdentity
from redot_compat.runner.process import ProcessResult


def read_extension_api(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngineError(f"extension API snapshot is not valid UTF-8 JSON: {exc}") from exc
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("header"), dict)
        or not isinstance(payload.get("classes"), list)
    ):
        raise EngineError("extension API snapshot lacks required sections: header and classes")
    return payload


def extension_api_lineage(payload: dict[str, Any]) -> str:
    header = payload["header"]
    parts = [header.get(f"version_{part}") for part in ("major", "minor", "patch")]
    if any(type(part) is not int or part < 0 for part in parts):
        raise EngineError("extension API header lacks integer major/minor/patch version")
    return ".".join(str(part) for part in parts)


def review_dump_diagnostics(
    process: ProcessResult, engine: EngineIdentity | None = None
) -> list[str]:
    """Review diagnostics only after the caller has validated the complete JSON dump."""
    if process.timed_out:
        raise EngineError("extension API dump timed out")
    if process.stdout_truncated or process.stderr_truncated or process.combined_truncated:
        raise EngineError("extension API dump diagnostics were truncated")
    known_shutdown = (
        engine is not None
        and engine.product_name == "Redot"
        and engine.platform == "windows"
        and redot_release_line(engine.product_version) == "26.3"
        and engine.product_version.startswith("26.3.stable.official.")
    )
    warnings: list[str] = []
    if process.exit_code != 0:
        if not known_shutdown or process.exit_code not in (3221225477, -1073741819):
            raise EngineError(f"extension API dump exited {process.exit_code}")
        warnings.append(
            f"known Redot 26.3 shutdown access violation ({process.exit_code}) "
            "after a complete valid API dump"
        )
    text = "\n".join(
        Path(path).read_text(encoding="utf-8", errors="replace")
        for path in (process.stdout_path, process.stderr_path)
    )
    unexplained: list[str] = []
    for line in text.splitlines():
        if "ERROR" not in line.upper() and "WARNING" not in line.upper():
            continue
        if known_shutdown and re.fullmatch(
            r"\s*(?:ERROR: \d+ RID allocations of type '.+' were leaked at exit\.?|"
            r"WARNING: ObjectDB instances leaked at exit \(run with --verbose for details\)\.?)\s*",
            line,
        ):
            warnings.append(f"known Redot 26.3 shutdown diagnostic: {line.strip()}")
        else:
            unexplained.append(line)
    if unexplained:
        excerpt = " | ".join(unexplained[:3])[:1000]
        raise EngineError(f"extension API dump emitted diagnostics: {excerpt}")
    return warnings
