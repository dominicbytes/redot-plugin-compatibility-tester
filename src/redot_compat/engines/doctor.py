from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from pydantic import Field

from redot_compat.engines.identity import identify_engine
from redot_compat.errors import EngineError
from redot_compat.models.base import ContractModel
from redot_compat.models.engine import EngineIdentity

_MAX_CAPTURE = 1024 * 1024


class DoctorCheck(ContractModel):
    name: str
    passed: bool
    detail: str


class DoctorReport(ContractModel):
    engine: EngineIdentity
    checks: list[DoctorCheck] = Field(min_length=1)
    isolated_state: bool = True


def doctor_engine(
    binary: Path,
    *,
    product_hint: str,
    timeout_seconds: float = 30.0,
) -> DoctorReport:
    resolved = binary.expanduser().resolve()
    if not resolved.is_file():
        raise EngineError(f"engine binary does not exist: {resolved}")
    if timeout_seconds <= 0:
        raise EngineError("doctor timeout must be positive")

    with tempfile.TemporaryDirectory(prefix="redot-compat-doctor-") as state:
        environment = _isolated_environment(Path(state))
        version_output = _run_check(
            [str(resolved), "--version"], environment, timeout_seconds, "version"
        )
        help_output = _run_check([str(resolved), "--help"], environment, timeout_seconds, "help")
    identity = identify_engine(
        resolved,
        version_output=version_output,
        help_output=help_output,
        product_hint=product_hint,
    )
    return DoctorReport(
        engine=identity,
        checks=[
            DoctorCheck(name="version", passed=True, detail=identity.product_version),
            DoctorCheck(name="help", passed=True, detail="bounded help output captured and hashed"),
            DoctorCheck(name="debug_flag", passed=True, detail="doctor never invokes -d"),
        ],
    )


def _run_check(
    command: list[str], environment: dict[str, str], timeout_seconds: float, name: str
) -> str:
    try:
        completed = subprocess.run(  # noqa: S603 - explicit operator-selected engine, no shell
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=timeout_seconds,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EngineError(f"engine {name} check failed: {exc}") from exc
    output = (completed.stdout + completed.stderr)[:_MAX_CAPTURE]
    if completed.returncode != 0:
        raise EngineError(f"engine {name} check exited {completed.returncode}: {output.strip()}")
    if not output.strip():
        raise EngineError(f"engine {name} check produced no output")
    return output


def _isolated_environment(root: Path) -> dict[str, str]:
    environment: dict[str, str] = {}
    for key in ("PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "LANG"):
        if value := os.environ.get(key):
            environment[key] = value
    for name in ("home", "config", "cache", "data", "temp"):
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        if name == "home":
            environment.update({"HOME": str(path), "USERPROFILE": str(path)})
        elif name == "config":
            environment.update({"XDG_CONFIG_HOME": str(path), "APPDATA": str(path)})
        elif name == "cache":
            environment.update({"XDG_CACHE_HOME": str(path)})
        elif name == "data":
            environment.update({"XDG_DATA_HOME": str(path), "LOCALAPPDATA": str(path)})
        else:
            environment.update({"TMP": str(path), "TEMP": str(path), "TMPDIR": str(path)})
    return environment
