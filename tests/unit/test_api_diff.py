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


def test_enum_value_change_is_reported_once() -> None:
    def index(value: int):
        return build_api_index(
            {
                "header": {},
                "classes": [],
                "global_enums": [
                    {
                        "name": "Variant.Type",
                        "is_bitfield": False,
                        "values": [{"name": "TYPE_MAX", "value": value}],
                    }
                ],
            }
        )

    result = diff_api_indexes(index(39), index(40))
    assert [change.symbol for change in result.changed] == ["enum_value:Variant.Type.TYPE_MAX"]


def test_enum_member_addition_and_bitfield_changes_are_distinct() -> None:
    control = build_api_index({"global_enums": [{"name": "Mode", "values": []}]})
    candidate = build_api_index(
        {
            "global_enums": [
                {
                    "name": "Mode",
                    "is_bitfield": True,
                    "values": [{"name": "NEW", "value": 1}],
                },
                {"name": "NewEnum", "values": []},
            ]
        }
    )
    result = diff_api_indexes(control, candidate)
    assert result.added == ["enum:NewEnum", "enum_value:Mode.NEW"]
    assert [change.symbol for change in result.changed] == ["enum:Mode"]
    assert diff_api_indexes(candidate, control).removed == result.added


def test_api_diff_warns_about_incompatible_header_metadata() -> None:
    control = build_api_index({"header": {"precision": "single", "build_configuration": "debug"}})
    candidate = build_api_index(
        {"header": {"precision": "double", "build_configuration": "release"}}
    )
    result = diff_api_indexes(control, candidate)
    assert len(result.warnings) == 2
    assert "precision" in result.warnings[0]
    assert "build_configuration" in result.warnings[1]
    assert diff_api_indexes(control, control).warnings == []
