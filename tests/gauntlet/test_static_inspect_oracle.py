from __future__ import annotations

import io
import json
import subprocess
import sys
import tarfile
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ORACLE = json.loads((ROOT / "tests/gauntlet/oracles/G-01.json").read_text(encoding="utf-8"))


def _run(source: Path, output: Path) -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    command = [
        sys.executable,
        "-m",
        "redot_compat",
        "inspect",
        str(source),
        "--output",
        str(output),
        "--json",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    payload = json.loads((output / "result.json").read_text(encoding="utf-8"))
    return completed, payload


def _normalized(payload: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(payload)
    result.pop("run_id", None)
    result.pop("created_at", None)
    result["source"].pop("retrieved_at", None)
    return result


def test_static_baseline_matches_oracle_twice(tmp_path: Path) -> None:
    fixture = ROOT / ORACLE["baseline_fixture"]
    first_process, first = _run(fixture, tmp_path / "first")
    second_process, second = _run(fixture, tmp_path / "second")
    expected = ORACLE["expected"]

    assert first_process.returncode == expected["process_exit"]
    assert second_process.returncode == expected["process_exit"]
    assert first["source"]["archive_sha256"] == ORACLE["baseline_fixture_sha256"]
    assert first["classification"] == expected["classification"]
    assert first["inventory"]["package_kind"] == expected["package_kind"]
    assert first["inventory"]["plugin_roots"] == expected["plugin_roots"]
    assert first["port_candidate"] is expected["port_candidate"]
    assert len(first["phases"]) == expected["phase_count"]
    assert _normalized(first) == _normalized(second)


def test_hostile_archives_are_rejected_without_source_tree(tmp_path: Path) -> None:
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir()
    zip_path = unsafe / "traversal.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("safe.txt", "safe")
        archive.writestr("../../escape.txt", "escape")
    tar_path = unsafe / "symlink.tar"
    with tarfile.open(tar_path, "w") as archive:
        info = tarfile.TarInfo("safe.txt")
        content = b"safe"
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        archive.addfile(link)

    for index, archive_path in enumerate((zip_path, tar_path)):
        output = tmp_path / f"rejected-{index}"
        process, payload = _run(archive_path, output)

        assert process.returncode == ORACLE["unsafe_expected"]["process_exit"]
        assert payload["classification"] == ORACLE["unsafe_expected"]["classification"]
        assert payload["findings"][0]["code"] == ORACLE["unsafe_expected"]["finding_code"]
        assert not (output / "workspace/source").exists()
        assert not (tmp_path / "escape.txt").exists()
        assert not (tmp_path / "outside").exists()
