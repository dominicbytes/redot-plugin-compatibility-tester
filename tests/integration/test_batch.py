from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from redot_compat.batch import runner
from redot_compat.batch.runner import run_batch
from redot_compat.models.batch import BatchItem, BatchManifest, BatchSummary
from redot_compat.models.result import CompatibilityResult


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


@pytest.mark.parametrize("change", ["definition", "report", "result"])
def test_resume_reruns_changed_or_incomplete_items(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    manifest = BatchManifest(items=[BatchItem(id="valid", source=str(fixture))])
    output = tmp_path / "batch"
    run_batch(manifest, output)
    if change == "definition":
        manifest.items[0].plugin_id = "changed"
    elif change == "report":
        (output / "items/valid/report.md").unlink()
    else:
        (output / "items/valid/result.json").write_text("{}")
    original = runner._run_item
    called: list[str] = []

    def run_item(item: BatchItem, *args: Any, **kwargs: Any) -> CompatibilityResult:
        called.append(item.id)
        return original(item, *args, **kwargs)

    monkeypatch.setattr(runner, "_run_item", run_item)
    summary = run_batch(manifest, output, resume=True)
    assert called == ["valid"]
    assert summary.resumed == 0
    assert summary.completed == 1
    assert summary.items[0].state == "completed"
    assert summary.items[0].classification is not None


def test_interruption_leaves_valid_incremental_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    output = tmp_path / "batch"
    manifest = BatchManifest(
        concurrency=1,
        items=[BatchItem(id=name, source=str(fixture)) for name in ("one", "two")],
    )
    original = runner._run_item
    snapshots: list[BatchSummary] = []
    original_write = runner._write_summary

    def write_summary(root: Path, summary: BatchSummary) -> None:
        original_write(root, summary)
        snapshots.append(
            BatchSummary.model_validate_json((root / "batch-summary.json").read_text())
        )

    def run_item(item: BatchItem, *args: Any, **kwargs: Any) -> CompatibilityResult:
        if item.id == "two":
            raise KeyboardInterrupt
        return original(item, *args, **kwargs)

    monkeypatch.setattr(runner, "_run_item", run_item)
    monkeypatch.setattr(runner, "_write_summary", write_summary)
    # Consume submission order so both completed futures cannot race this assertion.
    monkeypatch.setattr(runner, "as_completed", iter)
    with pytest.raises(KeyboardInterrupt):
        run_batch(manifest, output)
    summary = BatchSummary.model_validate_json((output / "batch-summary.json").read_text())
    assert summary.complete is False
    assert summary.interrupted is True
    assert summary.completed == 1
    assert summary.pending == 1
    assert [item.state for item in summary.items] == ["completed", "pending"]
    assert any(s.completed == 1 and not s.complete and not s.interrupted for s in snapshots)


def test_batch_forwards_tokens_without_persisting_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures/baseline_gdscript_pass"
    manifest = BatchManifest(items=[BatchItem(id="valid", source=str(fixture))])
    original = runner.inspect_source
    received: dict[str, str | None] = {}

    def inspect(
        *args: Any,
        github_token: str | None = None,
        codeberg_token: str | None = None,
        **kwargs: Any,
    ) -> CompatibilityResult:
        received.update(github=github_token, codeberg=codeberg_token)
        return original(*args, **kwargs)

    monkeypatch.setattr(runner, "inspect_source", inspect)
    output = tmp_path / "batch"
    summary = run_batch(manifest, output, github_token="gh-secret", codeberg_token="cb-secret")
    assert summary.completed == 1
    assert received == {"github": "gh-secret", "codeberg": "cb-secret"}
    assert "secret" not in (output / "batch-summary.json").read_text()
    assert "secret" not in (output / "items/valid/item.json").read_text()


def test_batch_resume_rechecks_changed_archive_limits(tmp_path: Path) -> None:
    import zipfile

    from redot_compat.config import ArchiveLimits

    archive = tmp_path / "plugin.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("addons/example/plugin.cfg", '[plugin]\nname="Example"\n')
        stream.writestr("addons/example/plugin.gd", "@tool\nextends EditorPlugin\n")
    manifest = BatchManifest(items=[BatchItem(id="one", source=str(archive))])
    output = tmp_path / "batch"
    assert run_batch(manifest, output).completed == 1
    summary = run_batch(manifest, output, resume=True, archive_limits=ArchiveLimits(max_entries=1))
    assert summary.resumed == 0
    assert summary.status_counts == {"INVALID_PACKAGE": 1}
