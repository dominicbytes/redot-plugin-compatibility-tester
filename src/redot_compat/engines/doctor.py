from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pydantic import Field

from redot_compat.archive.hash import sha256_file
from redot_compat.engines.extension_api import (
    extension_api_lineage,
    read_extension_api,
    review_dump_diagnostics,
)
from redot_compat.engines.identity import identify_engine
from redot_compat.engines.lineage import godot_lineage_for_redot
from redot_compat.errors import EngineError
from redot_compat.models.base import ContractModel
from redot_compat.models.engine import EngineIdentity
from redot_compat.runner.process import run_process

_MAX_CAPTURE = 1024 * 1024


class DoctorCheck(ContractModel):
    name: str
    passed: bool
    detail: str
    warning: bool = False


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
        work = Path(state) / "work"
        work.mkdir()
        process = run_process(
            [str(resolved), "--headless", "--dump-extension-api", "--quit-after", "2"],
            working_directory=work,
            environment=environment,
            output_directory=Path(state) / "logs",
            timeout_seconds=timeout_seconds,
        )
        if process.timed_out:
            raise EngineError("extension API dump timed out")
        snapshot = work / "extension_api.json"
        payload = read_extension_api(snapshot)
        lineage = extension_api_lineage(payload)
        header = payload["header"]
        if identity.product_name == "Redot":
            expected = godot_lineage_for_redot(identity.product_version)
            if expected is not None and expected != lineage:
                raise EngineError(
                    f"Redot lineage mismatch: table expects {expected}, "
                    f"API header reports {lineage}"
                )
        identity.compatibility_version = lineage
        if "precision" in header:
            precision = header["precision"]
            if not isinstance(precision, str):
                raise EngineError("extension API header precision must be a string")
            identity.precision = precision
        identity.extension_api_sha256 = sha256_file(snapshot)
        warnings = review_dump_diagnostics(process, identity)
    return DoctorReport(
        engine=identity,
        checks=[
            DoctorCheck(name="version", passed=True, detail=identity.product_version),
            DoctorCheck(name="help", passed=True, detail="bounded help output captured and hashed"),
            DoctorCheck(name="debug_flag", passed=True, detail="doctor never invokes -d"),
            DoctorCheck(
                name="extension_api",
                passed=True,
                detail=f"validated API header lineage {lineage}; precision={identity.precision}; "
                f"build_configuration={header.get('build_configuration')!r}; "
                f"sha256={identity.extension_api_sha256}",
            ),
            *[
                DoctorCheck(
                    name="extension_api_shutdown", passed=True, warning=True, detail=warning
                )
                for warning in warnings
            ],
        ],
    )


def _run_check(
    command: list[str], environment: dict[str, str], timeout_seconds: float, name: str
) -> str:
    with tempfile.TemporaryDirectory(prefix="redot-compat-check-") as state:
        try:
            process = run_process(
                command,
                working_directory=Path(state),
                environment=environment,
                output_directory=Path(state) / "logs",
                timeout_seconds=timeout_seconds,
                max_log_bytes=_MAX_CAPTURE,
            )
        except OSError as exc:
            raise EngineError(f"engine {name} check failed: {exc}") from exc
        if process.timed_out:
            raise EngineError(f"engine {name} check timed out")
        output = (
            Path(process.stdout_path).read_text(encoding="utf-8", errors="replace")
            + Path(process.stderr_path).read_text(encoding="utf-8", errors="replace")
        )[:_MAX_CAPTURE]
        if process.exit_code != 0:
            raise EngineError(f"engine {name} check exited {process.exit_code}: {output.strip()}")
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
