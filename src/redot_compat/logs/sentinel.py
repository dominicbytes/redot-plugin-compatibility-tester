from __future__ import annotations

import json

from pydantic import ValidationError

from redot_compat.errors import HarnessProtocolError
from redot_compat.models.phase import HarnessEvent

SENTINEL_PREFIX = "REDOT_COMPAT_EVENT "
_TERMINAL = {"pass", "fail", "error"}
_ALLOWED = {"start", "probe", *_TERMINAL}


def parse_harness_events(text: str, *, expected_run_id: str) -> list[HarnessEvent]:
    events: list[HarnessEvent] = []
    for line in text.splitlines():
        if not line.startswith(SENTINEL_PREFIX):
            continue
        try:
            raw = json.loads(line.removeprefix(SENTINEL_PREFIX))
            event = HarnessEvent.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise HarnessProtocolError(f"malformed harness event: {exc}") from exc
        events.append(event)
    if not events:
        raise HarnessProtocolError("no harness events were found")
    terminal_seen = False
    for expected_sequence, event in enumerate(events):
        if event.schema_version != 1:
            raise HarnessProtocolError("unsupported harness event schema")
        if event.run_id != expected_run_id:
            raise HarnessProtocolError("harness run_id does not match the owned run")
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
    if not terminal_seen:
        raise HarnessProtocolError("harness output has no terminal event")
    return events
