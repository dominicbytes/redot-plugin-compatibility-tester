from __future__ import annotations

import json
import shutil
import tomllib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, ValidationError

from redot_compat.inspect.service import inspect_source
from redot_compat.models.base import ContractModel
from redot_compat.models.batch import BatchItem, BatchManifest
from redot_compat.models.result import CompatibilityResult


class BatchSummary(ContractModel):
    total: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    resumed: int = Field(ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)


def load_batch_manifest(path: Path) -> BatchManifest:
    manifest_path = path.resolve(strict=True)
    payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = BatchManifest.model_validate(payload)
    items: list[BatchItem] = []
    for item in manifest.items:
        source = item.source
        if not urlsplit(source).scheme:
            candidate = Path(source)
            if not candidate.is_absolute():
                source = str((manifest_path.parent / candidate).resolve())
        items.append(item.model_copy(update={"source": source}))
    return manifest.model_copy(update={"items": items})


def run_batch(manifest: BatchManifest, output: Path, *, resume: bool = False) -> BatchSummary:
    root = output.resolve()
    if root.exists() and any(root.iterdir()) and not resume:
        raise ValueError(f"batch output must be new/empty unless --resume is used: {root}")
    (root / "items").mkdir(parents=True, exist_ok=True)
    completed: list[CompatibilityResult] = []
    failed = 0
    resumed = 0
    pending: list[BatchItem] = []
    for item in manifest.items:
        existing = _load_valid_result(root / "items" / item.id / "result.json") if resume else None
        if existing is not None:
            completed.append(existing)
            resumed += 1
        else:
            pending.append(item)
    with ThreadPoolExecutor(
        max_workers=manifest.concurrency, thread_name_prefix="compat-batch"
    ) as pool:
        futures = {pool.submit(_run_item, item, root): item for item in pending}
        for future in as_completed(futures):
            item = futures[future]
            try:
                completed.append(future.result())
            except Exception as exc:
                failed += 1
                _write_error(root / "items" / item.id, exc)
    counts = Counter(result.classification.value for result in completed)
    summary = BatchSummary(
        total=len(manifest.items),
        completed=len(completed),
        failed=failed,
        resumed=resumed,
        status_counts={key: counts[key] for key in sorted(counts)},
    )
    _write_summary(root, summary)
    return summary


def _run_item(item: BatchItem, root: Path) -> CompatibilityResult:
    item_root = root / "items" / item.id
    if item_root.exists():
        shutil.rmtree(item_root)
    return inspect_source(
        item.source,
        item_root,
        requested_ref=item.ref,
        release=item.release,
        asset_pattern=item.asset,
        plugin_id=item.plugin_id,
    )


def _load_valid_result(path: Path) -> CompatibilityResult | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CompatibilityResult.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError):
        return None


def _write_error(item_root: Path, error: Exception) -> None:
    item_root.mkdir(parents=True, exist_ok=True)
    payload = {"error_type": type(error).__name__, "message": str(error)[:2000]}
    (item_root / "error.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_summary(root: Path, summary: BatchSummary) -> None:
    payload = summary.model_dump(mode="json")
    (root / "batch-summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    counts = "\n".join(f"- `{key}`: {value}" for key, value in summary.status_counts.items())
    (root / "batch-summary.md").write_text(
        "# Batch summary\n\n"
        f"- Total: {summary.total}\n"
        f"- Completed: {summary.completed}\n"
        f"- Failed: {summary.failed}\n"
        f"- Resumed: {summary.resumed}\n\n"
        "## Status counts\n\n"
        f"{counts or '- No completed results.'}\n",
        encoding="utf-8",
        newline="\n",
    )
