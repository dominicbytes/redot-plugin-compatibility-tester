from __future__ import annotations

from redot_compat.engines.api_diff import diff_api_indexes
from redot_compat.engines.api_index import build_api_index


def test_api_diff_reports_added_removed_and_changed_symbols() -> None:
    control = build_api_index(
        {
            "header": {},
            "classes": [
                {
                    "name": "Node",
                    "methods": [
                        {"name": "old", "return_value": {"type": "int"}, "arguments": []},
                        {"name": "changed", "return_value": {"type": "int"}, "arguments": []},
                    ],
                }
            ],
        }
    )
    candidate = build_api_index(
        {
            "header": {},
            "classes": [
                {
                    "name": "Node",
                    "methods": [
                        {"name": "changed", "return_value": {"type": "String"}, "arguments": []},
                        {"name": "new", "return_value": {"type": "int"}, "arguments": []},
                    ],
                }
            ],
        }
    )

    result = diff_api_indexes(control, candidate)

    assert result.added == ["method:Node.new"]
    assert result.removed == ["method:Node.old"]
    assert [item.symbol for item in result.changed] == ["method:Node.changed"]
