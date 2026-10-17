from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import Field

from redot_compat.models.base import ContractModel


class ApiSymbol(ContractModel):
    kind: str
    owner: str | None = None
    name: str
    signature: str


class ApiIndex(ContractModel):
    engine_version: str | None = None
    precision: str | None = None
    build_configuration: str | None = None
    symbols: dict[str, ApiSymbol] = Field(default_factory=dict)


def load_api_index(path: Path) -> ApiIndex:
    """Load a saved index or a raw extension API dump, bounded to 512 MiB."""
    with path.open("rb") as stream:
        content = stream.read(512 * 1024 * 1024 + 1)
    if len(content) > 512 * 1024 * 1024:
        raise ValueError("API input exceeds 512 MiB")
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("API input root must be an object")
    if isinstance(payload.get("symbols"), dict):
        return ApiIndex.model_validate(payload)
    if isinstance(payload.get("header"), dict) and isinstance(payload.get("classes"), list):
        return build_api_index(payload)
    raise ValueError("API input must be a saved index or an extension API dump")


def build_api_index(snapshot: dict[str, Any]) -> ApiIndex:
    header = snapshot.get("header", {})
    symbols: dict[str, ApiSymbol] = {}
    for class_key in ("builtin_classes", "classes"):
        for class_item in _items(snapshot, class_key):
            owner = str(class_item.get("name", ""))
            if not owner:
                continue
            symbols[f"class:{owner}"] = ApiSymbol(
                kind="class",
                name=owner,
                signature=f"inherits={class_item.get('inherits') or ''}",
            )
            _add_members(symbols, owner, class_item, "methods", "method")
            _add_members(symbols, owner, class_item, "signals", "signal")
            _add_members(symbols, owner, class_item, "properties", "property")
            _add_members(symbols, owner, class_item, "members", "property")
            _add_members(symbols, owner, class_item, "constants", "constant")
            _add_enums(symbols, owner, class_item.get("enums", []))
    _add_members(symbols, None, snapshot, "utility_functions", "utility")
    _add_members(symbols, None, snapshot, "global_constants", "global_constant")
    _add_members(symbols, None, snapshot, "singletons", "singleton")
    for item in _items(snapshot, "native_structures"):
        name = str(item.get("name", ""))
        if name:
            symbols[f"native_structure:{name}"] = ApiSymbol(
                kind="native_structure", name=name, signature=str(item.get("format", ""))
            )
    _add_enums(symbols, None, snapshot.get("global_enums", []))
    return ApiIndex(
        engine_version=header.get("version_full_name"),
        precision=header.get("precision"),
        build_configuration=header.get("build_configuration"),
        symbols={key: symbols[key] for key in sorted(symbols)},
    )


def _items(container: dict[str, Any], key: str) -> Iterable[dict[str, Any]]:
    value = container.get(key, [])
    return (item for item in value if isinstance(item, dict))


def _add_members(
    symbols: dict[str, ApiSymbol],
    owner: str | None,
    container: dict[str, Any],
    source_key: str,
    kind: str,
) -> None:
    for item in _items(container, source_key):
        name = str(item.get("name", ""))
        if not name:
            continue
        prefix = f"{owner}." if owner else ""
        key = f"{kind}:{prefix}{name}"
        symbols[key] = ApiSymbol(
            kind=kind,
            owner=owner,
            name=name,
            signature=_signature(item),
        )


def _add_enums(symbols: dict[str, ApiSymbol], owner: str | None, enums: object) -> None:
    if not isinstance(enums, list):
        return
    for enum in (item for item in enums if isinstance(item, dict)):
        enum_name = str(enum.get("name", ""))
        if not enum_name:
            continue
        prefix = f"{owner}." if owner else ""
        symbols[f"enum:{prefix}{enum_name}"] = ApiSymbol(
            kind="enum",
            owner=owner,
            name=enum_name,
            signature=_signature({"is_bitfield": enum.get("is_bitfield", False)}),
        )
        values = enum.get("values", [])
        if not isinstance(values, list):
            continue
        for value in (item for item in values if isinstance(item, dict)):
            value_name = str(value.get("name", ""))
            if not value_name:
                continue
            symbols[f"enum_value:{prefix}{enum_name}.{value_name}"] = ApiSymbol(
                kind="enum_value",
                owner=owner,
                name=value_name,
                signature=_signature(value),
            )


def _signature(item: dict[str, Any]) -> str:
    relevant = {key: item[key] for key in sorted(item) if key not in {"description", "name"}}
    return json.dumps(relevant, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
