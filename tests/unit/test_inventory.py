from __future__ import annotations

from pathlib import Path

from redot_compat.inspect.inventory import inspect_plugin
from redot_compat.models import PackageKind

ROOT = Path(__file__).resolve().parents[2]


def test_detects_baseline_gdscript_plugin() -> None:
    fixture = ROOT / "tests/fixtures/baseline_gdscript_pass"

    inventory = inspect_plugin(fixture)

    assert inventory.plugin_roots == ["addons/example"]
    assert inventory.plugin_ids == ["example"]
    assert inventory.package_kind is PackageKind.GDSCRIPT
    assert inventory.contains_editor_plugin is True
    assert inventory.languages == ["GDScript"]


def test_keeps_multiple_roots_explicit(tmp_path: Path) -> None:
    for plugin_id in ("alpha", "beta"):
        root = tmp_path / "addons" / plugin_id
        root.mkdir(parents=True)
        (root / "plugin.cfg").write_text(
            f'[plugin]\nname="{plugin_id}"\nscript="plugin.gd"\n', encoding="utf-8"
        )
        (root / "plugin.gd").write_text("@tool\nextends EditorPlugin\n", encoding="utf-8")

    inventory = inspect_plugin(tmp_path)

    assert inventory.plugin_ids == ["alpha", "beta"]
    assert inventory.plugin_roots == ["addons/alpha", "addons/beta"]


def test_detects_engine_module_without_execution(tmp_path: Path) -> None:
    (tmp_path / "SCsub").write_text("", encoding="utf-8")
    (tmp_path / "register_types.cpp").write_text(
        "void initialize_example_module() {}", encoding="utf-8"
    )

    inventory = inspect_plugin(tmp_path)

    assert inventory.package_kind is PackageKind.ENGINE_MODULE
    assert inventory.contains_engine_module is True
