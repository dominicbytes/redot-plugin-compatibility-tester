from __future__ import annotations

from pathlib import Path

import pytest

from redot_compat.engines.snapshot import snapshot_engine

REDOT_ARCHIVE_SHA256 = "4644c7591bbe8019b861deb0ccdb64fd4f59a88514abf7c788cf176c259855af"


@pytest.mark.gauntlet
@pytest.mark.integration
def test_g02_redot_clean_archive_snapshot(request: pytest.FixtureRequest, tmp_path: Path) -> None:
    binary_value = request.config.getoption("--integration-redot")
    archive_value = request.config.getoption("--integration-redot-archive")
    expected = request.config.getoption("--integration-redot-archive-sha256")
    if not binary_value or not archive_value:
        pytest.skip("G-02 requires exact Redot binary and retained official archive")
    report = snapshot_engine(
        Path(binary_value),
        product_hint="redot",
        output_directory=tmp_path / "redot",
        archive=Path(archive_value),
        expected_archive_sha256=expected or REDOT_ARCHIVE_SHA256,
    )

    assert report.deterministic is True
    assert report.engine.product_version == "26.2.stable.official.4f5b14aba"
    assert report.engine.compatibility_version == "4.5.2"
    assert report.archive_sha256 == REDOT_ARCHIVE_SHA256
    assert report.snapshot_sha256 == report.runs[0].snapshot_sha256
    assert report.snapshot_sha256 == report.runs[1].snapshot_sha256


@pytest.mark.gauntlet
@pytest.mark.integration
def test_g02_exact_godot_control_snapshot(request: pytest.FixtureRequest, tmp_path: Path) -> None:
    binary_value = request.config.getoption("--integration-godot-control")
    if not binary_value:
        pytest.skip("G-02 exact-control check requires Godot 4.5.2")
    report = snapshot_engine(
        Path(binary_value),
        product_hint="godot",
        output_directory=tmp_path / "godot-control",
    )

    assert report.deterministic is True
    assert report.engine.product_version == "4.5.2.stable.official.6ce3de25a"
    assert report.engine.compatibility_version == "4.5.2"
    assert report.snapshot_sha256 == report.runs[0].snapshot_sha256
    assert report.snapshot_sha256 == report.runs[1].snapshot_sha256
