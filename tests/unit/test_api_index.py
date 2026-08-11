from __future__ import annotations

from redot_compat.engines.api_index import build_api_index


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
