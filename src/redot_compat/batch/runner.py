from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import ValidationError

from redot_compat.config import ArchiveLimits
from redot_compat.fsutil import atomic_write_text
from redot_compat.inspect.service import inspect_source
from redot_compat.models.batch import (
    BatchItem,
    BatchItemOutcome,
    BatchItemState,
    BatchManifest,
    BatchSummary,
)
from redot_compat.models.result import CompatibilityResult

ITEM_DEFINITION_FILE = "item.json"
SUMMARY_JSON = "batch-summary.json"
SUMMARY_MARKDOWN = "batch-summary.md"
# Files reports.render.write_reports always emits; a reusable item must have all
# of them (reproduce-manifest.json is conditional and therefore not required).
REQUIRED_REPORT_FILES = (
    "result.json",
    "report.md",
    "codex_port_brief.md",
    "reproduce.ps1",
    "reproduce.sh",
)

__all__ = [
    "BatchSummary",
    "item_fingerprint",
    "load_batch_manifest",
    "run_batch",
]


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


def item_fingerprint(item: BatchItem, *, archive_limits: ArchiveLimits | None = None) -> str:
    """SHA-256 of the canonical JSON of every field in the item definition."""

    payload = item.model_dump(mode="json")
    if archive_limits is not None:
        payload["archive_limits"] = archive_limits.model_dump(mode="json")
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _BatchState:
    """Main-thread-only bookkeeping that renders the (partial) summary."""

    def __init__(self, items: list[BatchItem], archive_limits: ArchiveLimits | None) -> None:
        self._items = items
        self._fingerprints = {
            item.id: item_fingerprint(item, archive_limits=archive_limits) for item in items
        }
        self._outcomes: dict[str, BatchItemOutcome] = {}

    def fingerprint(self, item: BatchItem) -> str:
        return self._fingerprints[item.id]

    def record_result(self, item: BatchItem, result: CompatibilityResult, *, resumed: bool) -> None:
        self._outcomes[item.id] = BatchItemOutcome(
            id=item.id,
            fingerprint=self.fingerprint(item),
            state=BatchItemState.RESUMED if resumed else BatchItemState.COMPLETED,
            classification=result.classification,
        )

    def record_failure(self, item: BatchItem, error: BaseException) -> None:
        self._outcomes[item.id] = BatchItemOutcome(
            id=item.id,
            fingerprint=self.fingerprint(item),
            state=BatchItemState.FAILED,
            error_type=type(error).__name__,
        )

    def summary(self, *, complete: bool, interrupted: bool = False) -> BatchSummary:
        outcomes = [
            self._outcomes.get(item.id)
            or BatchItemOutcome(
                id=item.id,
                fingerprint=self.fingerprint(item),
                state=BatchItemState.PENDING,
            )
            for item in self._items
        ]
        states = Counter(outcome.state for outcome in outcomes)
        counts = Counter(
            outcome.classification for outcome in outcomes if outcome.classification is not None
        )
        return BatchSummary(
            complete=complete,
            interrupted=interrupted,
            total=len(outcomes),
            completed=states[BatchItemState.COMPLETED] + states[BatchItemState.RESUMED],
            failed=states[BatchItemState.FAILED],
            resumed=states[BatchItemState.RESUMED],
            pending=states[BatchItemState.PENDING],
            status_counts={key: counts[key] for key in sorted(counts)},
            items=outcomes,
        )


def run_batch(
    manifest: BatchManifest,
    output: Path,
    *,
    resume: bool = False,
    archive_limits: ArchiveLimits | None = None,
    github_token: str | None = None,
    codeberg_token: str | None = None,
) -> BatchSummary:
    """Run every manifest item, rewriting the summary after each one finishes.

    The summary is marked ``complete: false`` until every item has a terminal
    state, so an interrupted run always leaves a readable partial summary. On
    ``KeyboardInterrupt`` queued items are cancelled, the partial summary is
    written with ``interrupted: true`` and the interrupt is re-raised.
    """

    root = output.resolve()
    if root.exists() and any(root.iterdir()) and not resume:
        raise ValueError(f"batch output must be new/empty unless --resume is used: {root}")
    (root / "items").mkdir(parents=True, exist_ok=True)
    state = _BatchState(manifest.items, archive_limits)
    pending: list[BatchItem] = []
    for item in manifest.items:
        existing = (
            _load_reusable_result(root / "items" / item.id, state.fingerprint(item))
            if resume
            else None
        )
        if existing is not None:
            state.record_result(item, existing, resumed=True)
        else:
            pending.append(item)
    _write_summary(root, state.summary(complete=not pending))

    pool = ThreadPoolExecutor(max_workers=manifest.concurrency, thread_name_prefix="compat-batch")
    try:
        futures: dict[Future[CompatibilityResult], BatchItem] = {
            pool.submit(
                _run_item,
                item,
                root,
                state.fingerprint(item),
                archive_limits=archive_limits,
                github_token=github_token,
                codeberg_token=codeberg_token,
            ): item
            for item in pending
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                state.record_result(item, future.result(), resumed=False)
            except Exception as exc:
                state.record_failure(item, exc)
                _write_error(root / "items" / item.id, exc)
            _write_summary(root, state.summary(complete=False))
    except BaseException:
        pool.shutdown(wait=False, cancel_futures=True)
        _write_summary(root, state.summary(complete=False, interrupted=True))
        raise
    pool.shutdown(wait=True)
    summary = state.summary(complete=True)
    _write_summary(root, summary)
    return summary


def _run_item(
    item: BatchItem,
    root: Path,
    fingerprint: str,
    *,
    archive_limits: ArchiveLimits | None = None,
    github_token: str | None = None,
    codeberg_token: str | None = None,
) -> CompatibilityResult:
    item_root = root / "items" / item.id
    if item_root.exists():
        shutil.rmtree(item_root)
    result = inspect_source(
        item.source,
        item_root,
        requested_ref=item.ref,
        archive_limits=archive_limits,
        release=item.release,
        asset_pattern=item.asset,
        plugin_id=item.plugin_id,
        github_token=github_token,
        codeberg_token=codeberg_token,
    )
    # Written last: its presence certifies the reports above belong to this
    # exact item definition.
    _write_json(
        item_root / ITEM_DEFINITION_FILE,
        {"fingerprint": fingerprint, "item": item.model_dump(mode="json")},
    )
    return result


def _load_reusable_result(item_root: Path, fingerprint: str) -> CompatibilityResult | None:
    """Return the stored result only if it provably belongs to this item definition."""

    if not all((item_root / name).is_file() for name in REQUIRED_REPORT_FILES):
        return None
    try:
        definition = json.loads((item_root / ITEM_DEFINITION_FILE).read_text(encoding="utf-8"))
        if not isinstance(definition, dict) or definition.get("fingerprint") != fingerprint:
            return None
        payload = json.loads((item_root / "result.json").read_text(encoding="utf-8"))
        return CompatibilityResult.model_validate(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError):
        return None


def _write_json(path: Path, payload: object) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_error(item_root: Path, error: Exception) -> None:
    item_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        item_root / "error.json",
        {"error_type": type(error).__name__, "message": str(error)[:2000]},
    )


def _write_summary(root: Path, summary: BatchSummary) -> None:
    _write_json(root / SUMMARY_JSON, summary.model_dump(mode="json"))
    counts = "\n".join(f"- `{key}`: {value}" for key, value in summary.status_counts.items())
    if summary.complete:
        status = "complete"
    elif summary.interrupted:
        status = "interrupted (partial)"
    else:
        status = "in progress (partial)"
    atomic_write_text(
        root / SUMMARY_MARKDOWN,
        "# Batch summary\n\n"
        f"- Status: {status}\n"
        f"- Total: {summary.total}\n"
        f"- Completed: {summary.completed}\n"
        f"- Failed: {summary.failed}\n"
        f"- Resumed: {summary.resumed}\n"
        f"- Pending: {summary.pending}\n\n"
        "## Status counts\n\n"
        f"{counts or '- No completed results.'}\n",
    )
