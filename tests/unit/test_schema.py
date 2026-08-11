from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from redot_compat.schema import generated_schemas

ROOT = Path(__file__).resolve().parents[2]


def test_checked_in_schemas_are_current() -> None:
    for filename, schema in generated_schemas().items():
        path = ROOT / "schemas" / filename
        assert path.exists(), filename
        assert json.loads(path.read_text(encoding="utf-8")) == schema


def test_generated_schemas_are_valid_draft_2020_12() -> None:
    for schema in generated_schemas().values():
        Draft202012Validator.check_schema(schema)
