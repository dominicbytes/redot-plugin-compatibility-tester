from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from redot_compat.models import (
    BatchManifest,
    CompatibilityResult,
    EngineIdentity,
    PluginInventory,
    PluginTestManifest,
    SourceProvenance,
)
from redot_compat.models.base import ContractModel


def generated_schemas() -> dict[str, dict[str, Any]]:
    models: dict[str, type[ContractModel]] = {
        "batch.schema.json": BatchManifest,
        "engine.schema.json": EngineIdentity,
        "inventory.schema.json": PluginInventory,
        "manifest.schema.json": PluginTestManifest,
        "result.schema.json": CompatibilityResult,
        "source.schema.json": SourceProvenance,
    }
    return {
        filename: model.model_json_schema(mode="serialization")
        for filename, model in sorted(models.items())
    }


def export_schemas(output_dir: Path, *, check: bool = False) -> list[Path]:
    expected = generated_schemas()
    changed: list[Path] = []
    if not check:
        output_dir.mkdir(parents=True, exist_ok=True)
    for filename, schema in expected.items():
        path = output_dir / filename
        content = _serialize(schema)
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            changed.append(path)
            if not check:
                path.write_text(content, encoding="utf-8", newline="\n")
    return changed


def _serialize(value: Mapping[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
