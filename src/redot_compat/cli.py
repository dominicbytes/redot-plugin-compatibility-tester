from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Annotated

import typer

from redot_compat.batch import load_batch_manifest, run_batch
from redot_compat.constants import APP_NAME, VERSION, ExitCode
from redot_compat.engines.api_diff import diff_api_indexes
from redot_compat.engines.api_index import build_api_index
from redot_compat.engines.doctor import doctor_engine
from redot_compat.engines.snapshot import snapshot_engine
from redot_compat.errors import RedotCompatError
from redot_compat.inspect.service import inspect_source
from redot_compat.models import CompatibilityResult, CompatibilityStatus
from redot_compat.reports.render import result_payload, write_reports
from redot_compat.schema import export_schemas, generated_schemas
from redot_compat.testing.service import test_source

app = typer.Typer(
    name=APP_NAME,
    help="Evidence-driven Redot plugin compatibility screening.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
)
schema_app = typer.Typer(help="Inspect or export versioned JSON Schemas.")
api_app = typer.Typer(help="Index or compare extension API snapshots.")
app.add_typer(schema_app, name="schema")
app.add_typer(api_app, name="api")


@app.command()
def version(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Print the CLI version."""
    if json_output:
        typer.echo(json.dumps({"name": APP_NAME, "version": VERSION}, sort_keys=True))
        return
    typer.echo(f"{APP_NAME} {VERSION}")


@schema_app.command("export")
def schema_export(
    output: Annotated[
        Path,
        typer.Option("--output", file_okay=False, dir_okay=True, resolve_path=True),
    ] = Path("schemas"),
    check: Annotated[
        bool,
        typer.Option("--check", help="Fail if checked-in schemas differ from generated schemas."),
    ] = False,
) -> None:
    """Export deterministic public JSON Schemas."""
    changed = export_schemas(output, check=check)
    if check and changed:
        names = ", ".join(path.name for path in changed)
        typer.echo(f"Schema files are stale or missing: {names}", err=True)
        raise typer.Exit(1)
    if not check:
        typer.echo(f"Exported {len(generated_schemas())} schemas to {output}")


@app.command("doctor")
def doctor_command(
    redot: Annotated[
        Path | None,
        typer.Option("--redot", help="Exact Redot executable; defaults to REDOT_BIN."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", file_okay=False, dir_okay=True, resolve_path=True),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the doctor report as JSON."),
    ] = False,
) -> None:
    """Hash and check an explicit Redot binary in isolated state."""
    configured = redot or (Path(value) if (value := os.environ.get("REDOT_BIN")) else None)
    if configured is None:
        typer.echo("doctor requires --redot or REDOT_BIN", err=True)
        raise typer.Exit(ExitCode.INCONCLUSIVE)
    output_path = output or Path("reports") / f"doctor-{uuid.uuid4()}"
    try:
        report = doctor_engine(configured, product_hint="redot")
    except RedotCompatError as exc:
        typer.echo(f"doctor failed: {exc}", err=True)
        raise typer.Exit(ExitCode.INCONCLUSIVE) from exc
    output_path.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump(mode="json", exclude_none=True)
    _write_json(output_path / "doctor.json", payload)
    _write_json(output_path / "engine.json", payload["engine"])
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(
            f"{report.engine.product_name} {report.engine.product_version}; "
            f"SHA-256 {report.engine.binary_sha256}; report: {output_path / 'doctor.json'}"
        )


@api_app.command("snapshot")
def api_snapshot_command(
    binary: Annotated[Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True)],
    product: Annotated[
        str, typer.Option("--product", help="Exact engine product: redot or godot.")
    ],
    output: Annotated[
        Path,
        typer.Option("--output", file_okay=False, dir_okay=True, resolve_path=True),
    ],
    archive: Annotated[
        Path | None,
        typer.Option("--archive", exists=True, dir_okay=False, resolve_path=True),
    ] = None,
    expected_archive_sha256: Annotated[
        str | None,
        typer.Option("--expected-archive-sha256"),
    ] = None,
) -> None:
    """Generate two isolated fresh extension API snapshots and require exact agreement."""
    normalized_product = product.casefold()
    if normalized_product not in {"redot", "godot"}:
        raise typer.BadParameter("--product must be redot or godot")
    try:
        report = snapshot_engine(
            binary,
            product_hint=normalized_product,  # type: ignore[arg-type]
            output_directory=output,
            archive=archive,
            expected_archive_sha256=expected_archive_sha256,
        )
    except RedotCompatError as exc:
        typer.echo(f"snapshot failed: {exc}", err=True)
        raise typer.Exit(ExitCode.INCONCLUSIVE) from exc
    typer.echo(
        f"{report.engine.product_name} {report.engine.product_version}; "
        f"snapshot SHA-256 {report.snapshot_sha256}; report: {output / 'snapshot.json'}"
    )


@api_app.command("index")
def api_index_command(
    snapshot: Annotated[Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True)],
    output: Annotated[
        Path,
        typer.Option("--output", dir_okay=False, resolve_path=True),
    ],
) -> None:
    """Create a deterministic symbol index from an extension API snapshot."""
    index = build_api_index(_load_json_object(snapshot))
    _write_json(output, index.model_dump(mode="json", exclude_none=True))
    typer.echo(f"Indexed {len(index.symbols)} symbols to {output}")


@api_app.command("diff")
def api_diff_command(
    control: Annotated[Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True)],
    candidate: Annotated[Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True)],
    output: Annotated[
        Path,
        typer.Option("--output", dir_okay=False, resolve_path=True),
    ],
) -> None:
    """Compare a control API snapshot with a candidate snapshot."""
    result = diff_api_indexes(
        build_api_index(_load_json_object(control)),
        build_api_index(_load_json_object(candidate)),
    )
    _write_json(output, result.model_dump(mode="json"))
    typer.echo(
        f"API diff: +{len(result.added)} -{len(result.removed)} "
        f"~{len(result.changed)}; report: {output}"
    )


@app.command("inspect")
def inspect_command(
    source: Annotated[str, typer.Argument(help="Local package path or supported repository URL.")],
    requested_ref: Annotated[
        str | None,
        typer.Option("--ref", help="Tag, branch, or commit to resolve immutably."),
    ] = None,
    release: Annotated[
        str | None,
        typer.Option("--release", help="Resolve latest or an exact release tag."),
    ] = None,
    asset_pattern: Annotated[
        str | None,
        typer.Option("--asset", help="Require exactly one matching release attachment."),
    ] = None,
    plugin_id: Annotated[
        str | None,
        typer.Option("--plugin-id", help="Select one root when a package contains several."),
    ] = None,
    force_test_baseline: Annotated[
        bool,
        typer.Option(
            "--force-test-baseline",
            help="Retain an explicit request for later gated testing despite baseline policy.",
        ),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", file_okay=False, dir_okay=True, resolve_path=True),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the authoritative result JSON to stdout."),
    ] = False,
) -> None:
    """Inspect source without executing plugin code."""
    output_path = output or Path("reports") / f"inspect-{uuid.uuid4()}"
    try:
        result = inspect_source(
            source,
            output_path,
            requested_ref=requested_ref,
            release=release,
            asset_pattern=asset_pattern,
            plugin_id=plugin_id,
            force_test_baseline=force_test_baseline,
        )
    except (OSError, RedotCompatError, ValueError) as exc:
        typer.echo(f"inspect failed: {exc}", err=True)
        raise typer.Exit(ExitCode.INTERNAL_ERROR) from exc
    if json_output:
        typer.echo(json.dumps(result_payload(result), sort_keys=True))
    else:
        typer.echo(
            f"{result.classification.value} ({result.confidence.value}); "
            f"result: {output_path / 'result.json'}"
        )
    raise typer.Exit(_exit_code(result.classification))


@app.command("test")
def test_command(
    source: Annotated[str, typer.Argument(help="Plugin source to inspect and test.")],
    redot: Annotated[
        Path | None,
        typer.Option("--redot", help="Exact Redot executable for trusted host mode."),
    ] = None,
    godot_control: Annotated[
        Path | None,
        typer.Option(
            "--godot-control",
            help="Exact Godot control executable for matched trusted-host phases.",
        ),
    ] = None,
    worker_image: Annotated[
        str | None,
        typer.Option(
            "--worker-image",
            help="Verified Linux worker image pinned as repository@sha256:digest.",
        ),
    ] = None,
    worker_engine_sha256: Annotated[
        str | None,
        typer.Option(
            "--worker-engine-sha256",
            help="Expected SHA-256 of /opt/redot/redot inside the pinned worker.",
        ),
    ] = None,
    manifest: Annotated[
        Path | None,
        typer.Option("--manifest", exists=True, dir_okay=False, resolve_path=True),
    ] = None,
    backend: Annotated[
        str,
        typer.Option("--backend", help="auto, docker, or host."),
    ] = "auto",
    trusted_source: Annotated[
        bool,
        typer.Option("--trusted-source", help="Affirm that the selected source is trusted."),
    ] = False,
    allow_unsafe_host: Annotated[
        bool,
        typer.Option(
            "--allow-unsafe-host-execution",
            help="Explicitly consent to non-sandboxed trusted host execution.",
        ),
    ] = False,
    requested_ref: Annotated[str | None, typer.Option("--ref")] = None,
    release: Annotated[str | None, typer.Option("--release")] = None,
    asset_pattern: Annotated[str | None, typer.Option("--asset")] = None,
    plugin_id: Annotated[str | None, typer.Option("--plugin-id")] = None,
    force_test_baseline: Annotated[
        bool,
        typer.Option("--force-test-baseline", help="Override the baseline policy skip."),
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", file_okay=False, dir_okay=True, resolve_path=True),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Run policy-aware phases only through an explicitly eligible backend."""
    output_path = output or Path("reports") / f"test-{uuid.uuid4()}"
    try:
        result = test_source(
            source,
            output_path,
            redot=redot,
            godot_control=godot_control,
            worker_image=worker_image,
            worker_engine_sha256=worker_engine_sha256,
            manifest_path=manifest,
            requested_ref=requested_ref,
            release=release,
            asset_pattern=asset_pattern,
            plugin_id=plugin_id,
            backend=backend,
            trusted_source=trusted_source,
            allow_unsafe_host=allow_unsafe_host,
            force_test_baseline=force_test_baseline,
        )
    except (OSError, RedotCompatError, ValueError) as exc:
        typer.echo(f"test failed: {exc}", err=True)
        raise typer.Exit(ExitCode.INTERNAL_ERROR) from exc
    if json_output:
        typer.echo(json.dumps(result_payload(result), sort_keys=True))
    else:
        typer.echo(
            f"{result.classification.value} ({result.confidence.value}); "
            f"result: {output_path / 'result.json'}"
        )
    raise typer.Exit(_exit_code(result.classification))


@app.command("batch")
def batch_command(
    manifest: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, resolve_path=True),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", file_okay=False, dir_okay=True, resolve_path=True),
    ] = None,
    resume: Annotated[
        bool,
        typer.Option("--resume", help="Reuse schema-valid completed item results."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Run bounded, isolated static inspections from a TOML manifest."""
    output_path = output or Path("reports") / f"batch-{uuid.uuid4()}"
    try:
        summary = run_batch(load_batch_manifest(manifest), output_path, resume=resume)
    except (OSError, RedotCompatError, ValueError) as exc:
        typer.echo(f"batch failed: {exc}", err=True)
        raise typer.Exit(ExitCode.INTERNAL_ERROR) from exc
    payload = summary.model_dump(mode="json")
    if json_output:
        typer.echo(json.dumps(payload, sort_keys=True))
    else:
        typer.echo(
            f"Batch complete: {summary.completed}/{summary.total}; "
            f"failed: {summary.failed}; summary: {output_path / 'batch-summary.json'}"
        )
    if summary.failed:
        raise typer.Exit(ExitCode.INCONCLUSIVE)


@app.command("report")
def report_command(
    result_file: Annotated[
        Path,
        typer.Argument(exists=True, dir_okay=False, resolve_path=True),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", file_okay=False, dir_okay=True, resolve_path=True),
    ],
) -> None:
    """Regenerate derived reports from an authoritative result.json."""
    try:
        result = CompatibilityResult.model_validate_json(result_file.read_text(encoding="utf-8"))
        if output.exists() and any(output.iterdir()):
            raise ValueError(f"report output must be new or empty: {output}")
        write_reports(result, output)
    except (OSError, ValueError) as exc:
        typer.echo(f"report failed: {exc}", err=True)
        raise typer.Exit(ExitCode.INTERNAL_ERROR) from exc
    typer.echo(f"Regenerated reports in {output}")


def _exit_code(status: CompatibilityStatus) -> ExitCode:
    if status in {
        CompatibilityStatus.COMPATIBLE_UNCHANGED,
        CompatibilityStatus.COMPATIBLE_REPACKAGE_ONLY,
    }:
        return ExitCode.SUCCESS
    if status is CompatibilityStatus.NO_PORT_NEEDED_BASELINE_POLICY:
        return ExitCode.BASELINE_POLICY_SKIP
    if status.value.startswith("PORT_REQUIRED_") or status is CompatibilityStatus.ENGINE_API_GAP:
        return ExitCode.PORT_REQUIRED
    if status in {
        CompatibilityStatus.INVALID_PACKAGE,
        CompatibilityStatus.UPSTREAM_PACKAGE_FAILURE,
    }:
        return ExitCode.INVALID_OR_UPSTREAM
    if status is CompatibilityStatus.INTERNAL_TESTER_ERROR:
        return ExitCode.INTERNAL_ERROR
    return ExitCode.INCONCLUSIVE


def _load_json_object(path: Path) -> dict[str, object]:
    if path.stat().st_size > 512 * 1024 * 1024:
        raise typer.BadParameter("API snapshot exceeds 512 MiB")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise typer.BadParameter("API snapshot root must be an object")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    app()
