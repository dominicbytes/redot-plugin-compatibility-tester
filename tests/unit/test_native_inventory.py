from __future__ import annotations

from pathlib import Path

from redot_compat.inspect.inventory import inspect_plugin


def test_gdextension_records_selectors_and_missing_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "addons/example"
    root.mkdir(parents=True)
    (root / "example.gdextension").write_text(
        '[configuration]\nentry_symbol="example_init"\ncompatibility_minimum="4.5"\n\n'
        '[libraries]\nwindows.debug.x86_64="res://addons/example/bin/example.dll"\n'
        'linux.release.x86_64="res://addons/example/bin/libexample.so"\n',
        encoding="utf-8",
    )

    inventory = inspect_plugin(tmp_path)

    assert inventory.contains_gdextension is True
    assert inventory.native_platforms == ["linux", "windows"]
    assert inventory.native_architectures == ["x86_64"]
    assert [item.exists for item in inventory.native_libraries] == [False, False]
    assert {item.entry_symbol for item in inventory.native_libraries} == {"example_init"}
