from __future__ import annotations

from redot_compat.runner.redaction import (
    StreamRedactor,
    redact_args,
    redact_environment,
    redact_text,
)


def test_environment_redacts_secret_names() -> None:
    value = redact_environment({"PATH": "safe", "GITHUB_TOKEN": "top-secret"})

    assert value == {"GITHUB_TOKEN": "<redacted>", "PATH": "safe"}


def test_argument_and_url_redaction() -> None:
    args = redact_args(["--token", "abc", "https://user:pass@example.test/file"])

    assert args == ["--token", "<redacted>", "https://<redacted>@example.test/file"]


def test_text_redacts_known_secret_values() -> None:
    assert redact_text("token=abc123", secrets=["abc123"]) == "token=<redacted>"


def test_stream_redactor_keeps_raw_tail_for_overlapping_secrets() -> None:
    redactor = StreamRedactor(["abc", "abcdef"])
    output = redactor.feed("abc") + redactor.feed("def!") + redactor.flush()
    assert output == "<redacted>!"


def test_stream_redactor_handles_every_split_without_reprocessing_markers() -> None:
    text = "prefix token-value and red suffix"
    for split in range(len(text) + 1):
        redactor = StreamRedactor(["token-value", "red"])
        result = redactor.feed(text[:split]) + redactor.feed(text[split:]) + redactor.flush()
        assert result == "prefix <redacted> and <redacted> suffix"


def test_stream_redactor_flushes_partial_prefix_and_empty_secret_list() -> None:
    redactor = StreamRedactor(["abcdef"])
    assert redactor.feed("abc") + redactor.flush() == "abc"
    redactor = StreamRedactor()
    assert redactor.feed("abc") + redactor.flush() == "abc"
