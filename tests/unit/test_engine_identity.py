from __future__ import annotations

from pathlib import Path

from redot_compat.engines.identity import identify_engine, parse_engine_version


def test_parse_redot_version_keeps_product_and_compatibility_separate() -> None:
    parsed = parse_engine_version("26.2.stable.official.4f5b14aba", product_hint="redot")

    assert parsed.product_name == "Redot"
    assert parsed.product_version == "26.2.stable.official.4f5b14aba"
    assert parsed.compatibility_version == "4.5.2"


def test_identify_engine_hashes_binary_and_help(tmp_path: Path) -> None:
    binary = tmp_path / "redot.exe"
    binary.write_bytes(b"not an executable")

    identity = identify_engine(
        binary,
        version_output="26.2.stable.official.4f5b14aba\n",
        help_output="Usage: redot [options]\n",
        product_hint="redot",
    )

    assert identity.binary_path == str(binary.resolve())
    assert len(identity.binary_sha256) == 64
    assert len(identity.help_output_sha256 or "") == 64
    assert identity.is_dotnet is False
