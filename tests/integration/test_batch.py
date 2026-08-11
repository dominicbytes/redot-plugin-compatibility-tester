from __future__ import annotations

import json
from pathlib import Path

from redot_compat.batch.runner import run_batch
from redot_compat.models.batch import BatchItem, BatchManifest


def test_batch_isolates_failures_and_resumes_valid_results(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    output = tmp_path / "batch"
    manifest = BatchManifest(
        concurrency=2,
        items=[
            BatchItem(id="valid", source=str(fixture)),
            BatchItem(id="missing", source=str(tmp_path / "does-not-exist")),
        ],
    )

    first = run_batch(manifest, output)
    result_mtime = (output / "items/valid/result.json").stat().st_mtime_ns
    second = run_batch(manifest, output, resume=True)

    assert first.completed == 1
    assert first.failed == 1
    assert second.resumed == 1
    assert (output / "items/valid/result.json").stat().st_mtime_ns == result_mtime
    summary = json.loads((output / "batch-summary.json").read_text(encoding="utf-8"))
    assert sum(summary["status_counts"].values()) == 1
