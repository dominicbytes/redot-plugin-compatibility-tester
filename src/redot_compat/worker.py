from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from redot_compat.exit_codes import exit_code_for
from redot_compat.reports import write_reports
from redot_compat.sandbox.heartbeat import start_controller_watchdog
from redot_compat.sandbox.worker_protocol import WorkerRequest
from redot_compat.testing.service import run_compatibility_test

INPUT_ROOT = Path("/input")
OUTPUT_ROOT = Path("/output")
ENGINE = Path("/opt/redot/redot")


def main() -> None:
    start_controller_watchdog()
    parser = argparse.ArgumentParser(description="Fixed redot-compat container worker")
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args()
    try:
        request_path = _inside(args.request, OUTPUT_ROOT)
        request = WorkerRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
        if _sha256(ENGINE) != request.engine_sha256:
            raise ValueError("worker engine SHA-256 does not match the request")
        source = (
            INPUT_ROOT if request.source_subpath == "." else INPUT_ROOT / request.source_subpath
        )
        source = _inside(source, INPUT_ROOT)
        output = _inside(OUTPUT_ROOT / request.output_subpath, OUTPUT_ROOT, must_exist=False)
        manifest_path: Path | None = None
        if request.manifest is not None:
            manifest_path = OUTPUT_ROOT / f".{request.run_id}-manifest.json"
            manifest_path.write_text(
                request.manifest.model_dump_json(indent=2, exclude_unset=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        result = run_compatibility_test(
            str(source),
            output,
            redot=ENGINE,
            manifest_path=manifest_path,
            backend="host",
            trusted_source=True,
            allow_unsafe_host=True,
            force_test_baseline=True,
            phase_timeouts=request.phase_timeouts,
            archive_limits=request.archive_limits,
        )
        result = result.model_copy(
            update={
                "sandbox": "docker_linux",
                "limitations": [
                    item
                    for item in result.limitations
                    if not item.startswith("Trusted host execution")
                ],
            }
        )
        write_reports(result, output)
    except (OSError, ValueError, ValidationError) as exc:
        error_path = OUTPUT_ROOT / "worker-error.json"
        error_path.write_text(
            json.dumps({"error": type(exc).__name__, "message": str(exc)[:2000]}, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        raise SystemExit(50) from exc
    raise SystemExit(exit_code_for(result.classification))


def _inside(path: Path, root: Path, *, must_exist: bool = True) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=must_exist)
    if not resolved.is_relative_to(resolved_root):
        raise ValueError(f"worker path escapes {resolved_root}")
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
