from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import Field

from redot_compat.archive.hash import sha256_file
from redot_compat.engines.doctor import doctor_engine
from redot_compat.errors import EngineError
from redot_compat.models.base import ContractModel
from redot_compat.models.engine import EngineIdentity
from redot_compat.runner.environment import build_isolated_environment
from redot_compat.runner.process import ProcessResult, run_process


class SnapshotRun(ContractModel):
    run_number: int = Field(ge=1, le=2)
    snapshot_path: str
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    process: ProcessResult


class EngineSnapshotReport(ContractModel):
    engine: EngineIdentity
    product_hint: Literal["redot", "godot"]
    archive_path: str | None = None
    archive_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    expected_archive_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    runs: list[SnapshotRun] = Field(min_length=2, max_length=2)
    deterministic: bool
    snapshot_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def snapshot_engine(
    binary: Path,
    *,
    product_hint: Literal["redot", "godot"],
    output_directory: Path,
    archive: Path | None = None,
    expected_archive_sha256: str | None = None,
    timeout_seconds: float = 30,
) -> EngineSnapshotReport:
    output = output_directory.resolve()
    if output.exists():
        if any(output.iterdir()):
            raise EngineError(f"snapshot output must be new or empty: {output}")
    else:
        output.mkdir(parents=True)
    if timeout_seconds <= 0:
        raise EngineError("snapshot timeout must be positive")
    engine = doctor_engine(
        binary, product_hint=product_hint, timeout_seconds=timeout_seconds
    ).engine
    archive_path: str | None = None
    archive_sha256: str | None = None
    normalized_expected = expected_archive_sha256.casefold() if expected_archive_sha256 else None
    if normalized_expected is not None and len(normalized_expected) != 64:
        raise EngineError("expected archive SHA-256 must contain 64 hexadecimal characters")
    if archive is not None:
        resolved_archive = archive.resolve(strict=True)
        archive_path = str(resolved_archive)
        archive_sha256 = sha256_file(resolved_archive)
        if normalized_expected is not None and archive_sha256 != normalized_expected:
            raise EngineError(
                f"archive SHA-256 mismatch: expected {normalized_expected}, got {archive_sha256}"
            )
    elif normalized_expected is not None:
        raise EngineError("expected archive SHA-256 requires an archive path")

    runs: list[SnapshotRun] = []
    for run_number in (1, 2):
        run_root = output / f"run-{run_number}"
        work = run_root / "work"
        work.mkdir(parents=True)
        environment = build_isolated_environment(run_root / "state")
        process = run_process(
            [
                engine.binary_path,
                "--headless",
                "--dump-extension-api",
                "--quit-after",
                "2",
            ],
            working_directory=work,
            environment=environment,
            output_directory=run_root / "logs",
            timeout_seconds=timeout_seconds,
        )
        if process.timed_out:
            raise EngineError(f"extension API dump {run_number} timed out")
        if process.exit_code != 0:
            raise EngineError(
                f"extension API dump {run_number} exited {process.exit_code}; "
                f"see {process.combined_log_path}"
            )
        snapshot = work / "extension_api.json"
        if not snapshot.is_file():
            raise EngineError(f"extension API dump {run_number} produced no extension_api.json")
        _reject_unexplained_engine_diagnostics(process, run_number)
        runs.append(
            SnapshotRun(
                run_number=run_number,
                snapshot_path=str(snapshot),
                snapshot_sha256=sha256_file(snapshot),
                process=process,
            )
        )

    digest = validate_snapshot_pair(
        Path(runs[0].snapshot_path),
        Path(runs[1].snapshot_path),
    )
    report = EngineSnapshotReport(
        engine=engine,
        product_hint=product_hint,
        archive_path=archive_path,
        archive_sha256=archive_sha256,
        expected_archive_sha256=normalized_expected,
        runs=runs,
        deterministic=True,
        snapshot_sha256=digest,
    )
    (output / "snapshot.json").write_text(
        report.model_dump_json(indent=2, exclude_none=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def validate_snapshot_pair(first: Path, second: Path) -> str:
    first_bytes = first.read_bytes()
    second_bytes = second.read_bytes()
    if first_bytes != second_bytes:
        raise EngineError("fresh extension API snapshots are not byte-identical")
    try:
        payload = json.loads(first_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngineError(f"extension API snapshot is not valid UTF-8 JSON: {exc}") from exc
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("header"), dict)
        or not isinstance(payload.get("classes"), list)
    ):
        raise EngineError("extension API snapshot lacks required sections: header and classes")
    return sha256_file(first)


def _reject_unexplained_engine_diagnostics(process: ProcessResult, run_number: int) -> None:
    text = "\n".join(
        Path(path).read_text(encoding="utf-8", errors="replace")
        for path in (process.stdout_path, process.stderr_path)
    )
    diagnostics = [
        line for line in text.splitlines() if "ERROR" in line.upper() or "WARNING" in line.upper()
    ]
    if diagnostics:
        excerpt = " | ".join(diagnostics[:3])[:1000]
        raise EngineError(f"extension API dump {run_number} emitted diagnostics: {excerpt}")
