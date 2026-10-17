from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from redot_compat.config import AppConfig, load_config
from redot_compat.errors import ConfigurationError


def test_config_repr_and_dump_hide_tokens(tmp_path: Path) -> None:
    config = AppConfig(github_token=SecretStr("secret-token"), output_root=tmp_path / "out")

    assert "secret-token" not in repr(config)
    assert "secret-token" not in str(config.model_dump(mode="json"))


def test_load_config_uses_toml_values(tmp_path: Path) -> None:
    config_path = tmp_path / "redot-compat.toml"
    config_path.write_text(
        '[paths]\noutput_root = "reports"\n\n[limits]\nmax_entries = 42\n',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.output_root == tmp_path / "reports"
    assert config.archive_limits.max_entries == 42


def test_load_config_reads_tokens_and_import_timeout_without_disclosing_them(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'github_token="private-github"\ncodeberg_token="private-codeberg"\n'
        "[timeouts]\nimport=12\nparse=3\n",
        encoding="utf-8",
    )
    config = load_config(path)
    assert config.github_token is not None
    assert config.github_token.get_secret_value() == "private-github"
    assert config.codeberg_token is not None
    assert config.codeberg_token.get_secret_value() == "private-codeberg"
    assert config.phase_timeouts.import_phase == 12
    assert "private-github" not in repr(config)
    assert "private-codeberg" not in config.model_dump_json()


@pytest.mark.parametrize(
    "invalid",
    [
        'github_token=["never-expose-this"]',
        "[paths]\noutput_root=4",
        "[limits]\nmax_entries=0",
        "[limits]\nmax_expansion_ratio=inf",
        "[timeouts]\nparse=-1",
        "[timeouts]\nparse=nan",
        '[timeouts]\nunknown="never-expose-this"',
        'unknown="never-expose-this"',
        '[paths]\nunknown="never-expose-this"',
        'github_token="never-expose-this"\nmalformed=[',
    ],
)
def test_invalid_config_is_rejected_without_echoing_input(invalid: str, tmp_path: Path) -> None:
    path = tmp_path / "invalid.toml"
    path.write_text(invalid, encoding="utf-8")
    with pytest.raises(ConfigurationError) as error:
        load_config(path)
    assert "never-expose-this" not in str(error.value)
    assert "Invalid configuration" in str(error.value)


def test_missing_config_has_a_safe_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_config(tmp_path / "missing.toml")
