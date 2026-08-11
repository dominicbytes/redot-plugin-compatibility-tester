from __future__ import annotations

from redot_compat.runner.redaction import redact_args, redact_environment, redact_text


def test_environment_redacts_secret_names() -> None:
    value = redact_environment({"PATH": "safe", "GITHUB_TOKEN": "top-secret"})

    assert value == {"GITHUB_TOKEN": "<redacted>", "PATH": "safe"}


def test_argument_and_url_redaction() -> None:
    args = redact_args(["--token", "abc", "https://user:pass@example.test/file"])

    assert args == ["--token", "<redacted>", "https://<redacted>@example.test/file"]


def test_text_redacts_known_secret_values() -> None:
    assert redact_text("token=abc123", secrets=["abc123"]) == "token=<redacted>"
