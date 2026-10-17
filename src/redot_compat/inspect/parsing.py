from __future__ import annotations

import configparser
from pathlib import Path


def read_ini(path: Path) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser(interpolation=None, strict=False)
    try:
        text = path.read_text(encoding="utf-8-sig")
        parser.read_string("\n".join(_strip_comment(line) for line in text.splitlines()))
    except (configparser.Error, UnicodeError, OSError):
        return parser
    return parser


def unquote(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = _strip_comment(value).strip().lstrip("\ufeff")
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1]
    return stripped


def get_case_insensitive(
    parser: configparser.RawConfigParser, section: str, key: str
) -> str | None:
    if not parser.has_section(section):
        return None
    for candidate, value in parser.items(section):
        if candidate.casefold() == key.casefold():
            return unquote(value)
    return None


def _strip_comment(value: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\" and quote:
            escaped = True
        elif char == quote:
            quote = None
        elif char in {'"', "'"} and quote is None:
            quote = char
        elif char in {";", "#"} and quote is None:
            return value[:index]
    return value
