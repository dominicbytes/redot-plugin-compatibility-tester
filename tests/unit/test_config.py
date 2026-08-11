from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from redot_compat.config import AppConfig, load_config


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
