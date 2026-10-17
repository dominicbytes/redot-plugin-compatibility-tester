from __future__ import annotations

import hashlib
import hmac
import json
import re

from pydantic import ValidationError

from redot_compat.constants import HARNESS_EVENT_SCHEMA_VERSION
from redot_compat.errors import HarnessProtocolError
from redot_compat.models.phase import HarnessEvent

SENTINEL_PREFIX = "REDOT_COMPAT_EVENT "
_TERMINAL = {"pass", "fail", "error"}
_ALLOWED = {"start", "probe", *_TERMINAL}


class HarnessUnauthenticatedError(HarnessProtocolError):
    """An event cannot be attributed to the owned harness session."""


def parse_harness_events(
    text: str,
    *,
    expected_run_id: str,
    session_key: str,
    require_terminal: bool = True,
) -> list[HarnessEvent]:
    if re.fullmatch(r"[a-f0-9]{64}", session_key) is None:
        raise HarnessProtocolError("invalid harness session key")
    events: list[HarnessEvent] = []
    for line in text.splitlines():
        if not (line.startswith(SENTINEL_PREFIX) or line == SENTINEL_PREFIX.rstrip()):
            continue
        signature, separator, body = line.removeprefix(SENTINEL_PREFIX).partition(" ")
        expected = hmac.new(bytes.fromhex(session_key), body.encode("utf-8"), hashlib.sha256)
        if (
            not separator
            or re.fullmatch(r"[a-f0-9]{64}", signature) is None
            or not hmac.compare_digest(signature, expected.hexdigest())
        ):
            raise HarnessUnauthenticatedError("harness event MAC is missing or invalid")
        try:
            raw = json.loads(body)
            if isinstance(raw, dict) and (
                raw.get("schema") != HARNESS_EVENT_SCHEMA_VERSION
                or raw.get("run_id") != expected_run_id
            ):
                raise HarnessUnauthenticatedError("harness event schema or run_id does not match")
            event = HarnessEvent.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise HarnessProtocolError(f"malformed harness event: {exc}") from exc
        events.append(event)
    terminal_seen = False
    for expected_sequence, event in enumerate(events):
        if event.sequence != expected_sequence:
            raise HarnessProtocolError(
                "harness event sequence is missing, duplicated, or reordered"
            )
        if event.event not in _ALLOWED:
            raise HarnessProtocolError(f"unsupported harness event: {event.event}")
        if expected_sequence == 0 and event.event != "start":
            raise HarnessProtocolError("the first harness event must be start")
        if terminal_seen:
            raise HarnessProtocolError("events appeared after a terminal harness event")
        terminal_seen = event.event in _TERMINAL
    if require_terminal and not terminal_seen:
        raise HarnessProtocolError("harness output has no terminal event")
    return events
