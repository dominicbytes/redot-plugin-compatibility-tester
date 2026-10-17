from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import mock_open

import pytest

from redot_compat.engines.api_index import build_api_index, load_api_index


def test_api_index_is_deterministic_and_covers_member_kinds() -> None:
    snapshot = {
        "header": {"version_full_name": "Godot Engine v4.5.2"},
        "global_constants": [{"name": "GLOBAL", "value": 7}],
        "global_enums": [{"name": "Mode", "values": [{"name": "MODE_A", "value": 0}]}],
        "utility_functions": [{"name": "print_rich", "return_type": "Nil", "arguments": []}],
        "builtin_classes": [
            {
                "name": "Vector2",
                "members": [{"name": "x", "type": "float"}],
                "methods": [{"name": "length", "return_type": "float", "arguments": []}],
            }
        ],
        "classes": [
            {
                "name": "Node",
                "inherits": "Object",
                "methods": [
                    {
                        "name": "add_child",
                        "return_value": {"type": "void"},
                        "arguments": [{"name": "node", "type": "Node"}],
                    }
                ],
                "signals": [{"name": "ready", "arguments": []}],
                "properties": [{"name": "name", "type": "String"}],
                "constants": [{"name": "NOTIFICATION_READY", "value": 13}],
                "enums": [
                    {
                        "name": "ProcessMode",
                        "values": [{"name": "PROCESS_MODE_INHERIT", "value": 0}],
                    }
                ],
            }
        ],
    }

    first = build_api_index(snapshot)
    second = build_api_index(snapshot)

    assert first == second
    assert first.symbols["class:Node"].signature == "inherits=Object"
    assert "method:Node.add_child" in first.symbols
    assert "signal:Node.ready" in first.symbols
    assert "property:Node.name" in first.symbols
    assert "enum_value:Node.ProcessMode.PROCESS_MODE_INHERIT" in first.symbols
    assert "utility:print_rich" in first.symbols


def test_api_index_records_header_singletons_and_native_structures() -> None:
    index = build_api_index(
        {
            "header": {"precision": "double", "build_configuration": "debug"},
            "classes": [],
            "singletons": [{"name": "Engine", "type": "Engine"}],
            "native_structures": [{"name": "ObjectID", "format": "uint64_t id = 0"}],
        }
    )
    assert index.precision == "double"
    assert index.build_configuration == "debug"
    assert index.symbols["singleton:Engine"].kind == "singleton"
    assert index.symbols["singleton:Engine"].signature == '{"type":"Engine"}'
    assert index.symbols["native_structure:ObjectID"].kind == "native_structure"
    assert index.symbols["native_structure:ObjectID"].signature == "uint64_t id = 0"


def test_load_api_index_accepts_raw_dump_and_saved_index(tmp_path: Path) -> None:
    raw = tmp_path / "raw.json"
    saved = tmp_path / "index.json"
    raw.write_text(
        json.dumps(
            {"header": {}, "classes": [{"name": "Node", "methods": [{"name": "caf\u00e9"}]}]}
        )
    )
    index = load_api_index(raw)
    saved.write_text(index.model_dump_json(), encoding="utf-8")
    assert load_api_index(saved) == index
    assert "class:Node" in index.symbols


@pytest.mark.parametrize("payload", [[], {}, {"header": {}}, {"classes": []}, {"symbols": []}])
def test_load_api_index_rejects_unrecognized_json(tmp_path: Path, payload: object) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_api_index(path)


def test_load_api_index_limits_actual_read(monkeypatch: pytest.MonkeyPatch) -> None:
    class Oversized(bytes):
        def __len__(self) -> int:
            return 512 * 1024 * 1024 + 1

    opened = mock_open()
    opened.return_value.read.return_value = Oversized(b"{}")
    monkeypatch.setattr(Path, "open", opened)
    with pytest.raises(ValueError, match="512 MiB"):
        load_api_index(Path("oversized.json"))
    opened().read.assert_called_once_with(512 * 1024 * 1024 + 1)
