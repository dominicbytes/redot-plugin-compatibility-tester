from __future__ import annotations

from pathlib import Path

from redot_compat.inspect.inventory import inspect_plugin
from redot_compat.models import Confidence, VersionMeaning

ROOT = Path(__file__).resolve().parents[2]


def test_project_feature_is_decisive_for_pure_gdscript() -> None:
    inventory = inspect_plugin(ROOT / "tests/fixtures/baseline_gdscript_pass")

    assert inventory.effective_api_target == "4.5"
    assert inventory.effective_api_confidence is Confidence.HIGH
    assert any(
        item.meaning is VersionMeaning.PROJECT_FEATURE_VERSION
        for item in inventory.version_evidence
    )


def test_direct_native_target_overrides_weak_release_claim(tmp_path: Path) -> None:
    root = tmp_path / "addons/example"
    root.mkdir(parents=True)
    (root / "plugin.cfg").write_text(
        '[plugin]\nname="Example"\ngodot_version="4.0"\nscript="plugin.gd"\n',
        encoding="utf-8",
    )
    (root / "example.gdextension").write_text(
        '[configuration]\nentry_symbol="init"\ncompatibility_minimum="4.7"\n', encoding="utf-8"
    )

    inventory = inspect_plugin(tmp_path)

    assert inventory.effective_api_target == "4.7"
    assert inventory.version_conflicts
