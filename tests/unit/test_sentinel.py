from __future__ import annotations

import json

import pytest

from redot_compat.errors import HarnessProtocolError
from redot_compat.logs.sentinel import parse_harness_events


def _line(sequence: int, event: str, *, run_id: str = "run-abc") -> str:
    return "REDOT_COMPAT_EVENT " + json.dumps(
        {"schema": 1, "run_id": run_id, "sequence": sequence, "event": event, "payload": {}}
    )


def test_sentinel_accepts_one_ordered_terminal_sequence() -> None:
    events = parse_harness_events(
        "noise\n" + _line(0, "start") + "\n" + _line(1, "probe") + "\n" + _line(2, "pass"),
        expected_run_id="run-abc",
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
        parse_harness_events(text, expected_run_id="run-abc")
