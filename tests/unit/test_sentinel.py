from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from redot_compat.errors import HarnessProtocolError
from redot_compat.logs.sentinel import HarnessUnauthenticatedError, parse_harness_events

KEY = "ab" * 32


def _line(sequence: int, event: str, *, run_id: str = "run-abc") -> str:
    body = json.dumps(
        {"schema": 2, "run_id": run_id, "sequence": sequence, "event": event, "payload": {}}
    )
    mac = hmac.new(bytes.fromhex(KEY), body.encode(), hashlib.sha256).hexdigest()
    return f"REDOT_COMPAT_EVENT {mac} {body}"


def test_sentinel_accepts_one_ordered_terminal_sequence() -> None:
    events = parse_harness_events(
        "noise\n" + _line(0, "start") + "\n" + _line(1, "probe") + "\n" + _line(2, "pass"),
        expected_run_id="run-abc",
        session_key=KEY,
    )

    assert [event.event for event in events] == ["start", "probe", "pass"]


@pytest.mark.parametrize(
    "text",
    [
        _line(1, "start") + "\n" + _line(2, "pass"),
        _line(0, "start") + "\n" + _line(2, "pass"),
        _line(0, "start") + "\n" + _line(1, "pass") + "\n" + _line(2, "pass"),
        _line(0, "probe") + "\n" + _line(1, "pass"),
        _line(0, "start", run_id="wrong") + "\n" + _line(1, "pass", run_id="wrong"),
    ],
)
def test_sentinel_rejects_malformed_or_ambiguous_success(text: str) -> None:
    with pytest.raises(HarnessProtocolError):
        parse_harness_events(text, expected_run_id="run-abc", session_key=KEY)


@pytest.mark.parametrize(
    "line",
    [
        'REDOT_COMPAT_EVENT {"schema":2,"event":"pass"}',
        "REDOT_COMPAT_EVENT " + "0" * 64 + " {}",
        _line(0, "start", run_id="other-run"),
        _line(0, "start").replace('"schema": 2', '"schema": 1'),
    ],
)
def test_unauthenticated_events_are_distinct_from_protocol_corruption(line: str) -> None:
    with pytest.raises(HarnessUnauthenticatedError):
        parse_harness_events(line, expected_run_id="run-abc", session_key=KEY)


def test_authenticated_wrong_schema_is_unauthenticated() -> None:
    body = '{"schema":1,"run_id":"run-abc","sequence":0,"event":"start","payload":{}}'
    mac = hmac.new(bytes.fromhex(KEY), body.encode(), hashlib.sha256).hexdigest()
    with pytest.raises(HarnessUnauthenticatedError):
        parse_harness_events(
            f"REDOT_COMPAT_EVENT {mac} {body}", expected_run_id="run-abc", session_key=KEY
        )


def test_mac_covers_exact_utf8_body() -> None:
    body = '{"schema":2,"run_id":"run-abc","sequence":0,"event":"start","payload":{"text":"caf?"}}'
    mac = hmac.new(bytes.fromhex(KEY), body.encode("utf-8"), hashlib.sha256).hexdigest()
    text = f"REDOT_COMPAT_EVENT {mac} {body}"
    assert parse_harness_events(
        text, expected_run_id="run-abc", session_key=KEY, require_terminal=False
    )
    with pytest.raises(HarnessUnauthenticatedError):
        parse_harness_events(text + " ", expected_run_id="run-abc", session_key=KEY)


def test_incomplete_events_can_be_retained_without_proving_success() -> None:
    assert (
        parse_harness_events(
            "noise", expected_run_id="run-abc", session_key=KEY, require_terminal=False
        )
        == []
    )
    with pytest.raises(HarnessProtocolError, match="no terminal"):
        parse_harness_events(_line(0, "start"), expected_run_id="run-abc", session_key=KEY)
