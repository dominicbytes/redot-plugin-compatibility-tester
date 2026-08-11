from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

REDACTED = "<redacted>"
_SECRET_KEY = re.compile(
    r"(?:token|secret|password|passwd|credential|authorization|api[_-]?key|private[_-]?key)",
    re.IGNORECASE,
)
_SECRET_FLAGS = {
    "--token",
    "--password",
    "--secret",
    "--authorization",
    "--api-key",
}


def redact_environment(environment: Mapping[str, str]) -> dict[str, str]:
    return {
        key: REDACTED if _SECRET_KEY.search(key) else redact_url(value)
        for key, value in sorted(environment.items())
    }


def redact_args(arguments: Sequence[str]) -> list[str]:
    redacted: list[str] = []
    hide_next = False
    for argument in arguments:
        if hide_next:
            redacted.append(REDACTED)
            hide_next = False
            continue
        lowered = argument.lower()
        if lowered in _SECRET_FLAGS:
            redacted.append(argument)
            hide_next = True
            continue
        if "=" in argument:
            key, value = argument.split("=", 1)
            if _SECRET_KEY.search(key):
                redacted.append(f"{key}={REDACTED}")
                continue
            argument = f"{key}={redact_url(value)}"
        redacted.append(redact_url(argument))
    return redacted


def redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if not parsed.scheme or not parsed.netloc or parsed.username is None:
        return value
    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port is not None else ""
    return urlunsplit(
        (parsed.scheme, f"{REDACTED}@{hostname}{port}", parsed.path, parsed.query, parsed.fragment)
    )


def redact_text(value: str, *, secrets: Iterable[str] = ()) -> str:
    result = value
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        result = result.replace(secret, REDACTED)
    return result
