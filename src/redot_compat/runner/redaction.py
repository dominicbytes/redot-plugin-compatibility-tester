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


class StreamRedactor:
    """Redact known secret values from text that arrives in arbitrary chunks.

    Any trailing text that could still be the beginning of a secret is held back
    until more input arrives (or the stream is flushed), so a secret split across
    chunk boundaries is still replaced as a whole.
    """

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self._secrets = tuple(sorted({item for item in secrets if item}, key=len, reverse=True))
        self._pattern = (
            re.compile("|".join(re.escape(item) for item in self._secrets))
            if self._secrets
            else None
        )
        self._tail_length = max((len(item) for item in self._secrets), default=1) - 1
        self._pending = ""

    def feed(self, text: str) -> str:
        if self._pattern is None:
            return text
        self._pending += text
        safe_end = max(0, len(self._pending) - self._tail_length)
        position = 0
        output: list[str] = []
        for match in self._pattern.finditer(self._pending):
            if match.start() >= safe_end:
                break
            output.extend((self._pending[position : match.start()], REDACTED))
            position = match.end()
        end = max(position, safe_end)
        output.append(self._pending[position:end])
        self._pending = self._pending[end:]
        return "".join(output)

    def flush(self) -> str:
        remaining = (
            self._pattern.sub(lambda _: REDACTED, self._pending)
            if self._pattern is not None
            else self._pending
        )
        self._pending = ""
        return remaining
