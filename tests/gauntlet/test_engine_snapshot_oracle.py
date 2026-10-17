from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from redot_compat.engines.lineage import godot_lineage_for_redot, redot_release_line
from redot_compat.engines.snapshot import snapshot_engine

REDOT_ARCHIVE_SHA256 = "4644c7591bbe8019b861deb0ccdb64fd4f59a88514abf7c788cf176c259855af"


@pytest.mark.gauntlet
@pytest.mark.integration
def test_g02_redot_clean_archive_snapshot(request: pytest.FixtureRequest) -> None:
    binary_value = request.config.getoption("--integration-redot")
    archive_value = request.config.getoption("--integration-redot-archive")
    expected = request.config.getoption("--integration-redot-archive-sha256")
    if not binary_value:
        pytest.skip("G-02 requires an exact Redot binary")
    with TemporaryDirectory(prefix="compatester-oracle-redot-") as output:
        report = snapshot_engine(
            Path(binary_value),
            product_hint="redot",
            output_directory=Path(output) / "redot",
            archive=Path(archive_value) if archive_value else None,
            expected_archive_sha256=expected,
        )

    assert report.deterministic is True
    assert redot_release_line(report.engine.product_version) in {"26.2", "26.3"}
    assert report.engine.compatibility_version == "4.5.2"
    assert report.engine.compatibility_version == godot_lineage_for_redot(
        report.engine.product_version
    )
    if archive_value and redot_release_line(report.engine.product_version) == "26.2":
        assert report.archive_sha256 == (expected or REDOT_ARCHIVE_SHA256)
    if expected:
        assert report.archive_sha256 == expected
    assert report.snapshot_sha256 == report.runs[0].snapshot_sha256
    assert report.snapshot_sha256 == report.runs[1].snapshot_sha256


@pytest.mark.gauntlet
@pytest.mark.integration
def test_g02_exact_godot_control_snapshot(request: pytest.FixtureRequest) -> None:
    binary_value = request.config.getoption("--integration-godot-control")
    if not binary_value:
        pytest.skip("G-02 exact-control check requires Godot 4.5.2")
    with TemporaryDirectory(prefix="compatester-oracle-godot-") as output:
        report = snapshot_engine(
            Path(binary_value),
            product_hint="godot",
            output_directory=Path(output) / "godot-control",
        )

    assert report.deterministic is True
    assert report.engine.product_version == "4.5.2.stable.official.6ce3de25a"
    assert report.engine.compatibility_version == "4.5.2"
    assert report.snapshot_sha256 == report.runs[0].snapshot_sha256
    assert report.snapshot_sha256 == report.runs[1].snapshot_sha256
