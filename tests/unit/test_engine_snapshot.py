from __future__ import annotations

import json
from pathlib import Path

import pytest

from redot_compat.engines.snapshot import validate_snapshot_pair
from redot_compat.errors import EngineError


def test_snapshot_pair_requires_identical_structured_api(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    payload = {"header": {"version_full_name": "4.5.2"}, "classes": [{"name": "Node"}]}
    encoded = json.dumps(payload, sort_keys=True).encode()
    first.write_bytes(encoded)
    second.write_bytes(encoded)

    digest = validate_snapshot_pair(first, second)

    assert digest == validate_snapshot_pair(second, first)


def test_snapshot_pair_rejects_drift(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text('{"header":{},"classes":[]}', encoding="utf-8")
    second.write_text('{"header":{},"classes":[{"name":"Node"}]}', encoding="utf-8")

    with pytest.raises(EngineError, match="not byte-identical"):
        validate_snapshot_pair(first, second)


def test_snapshot_pair_rejects_missing_sections(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text('{"header":{}}', encoding="utf-8")
    second.write_text('{"header":{}}', encoding="utf-8")

    with pytest.raises(EngineError, match="required sections"):
        validate_snapshot_pair(first, second)
