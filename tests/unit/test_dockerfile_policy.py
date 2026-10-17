from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_worker_recipe_is_pinned_verified_and_non_root() -> None:
    dockerfile = (ROOT / "docker/Dockerfile.worker").read_text(encoding="utf-8")

    assert "FROM python:3.12.13-slim-bookworm@sha256:" in dockerfile
    assert "sha256sum --check --strict" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "--require-hashes" in dockerfile
    assert 'ENTRYPOINT ["python", "-m", "redot_compat.worker"]' in dockerfile
    assert ":latest" not in dockerfile


def test_download_tools_stay_in_builder_and_archive_selection_is_exact() -> None:
    dockerfile = (ROOT / "docker/Dockerfile.worker").read_text(encoding="utf-8")
    builder, final = dockerfile.split("\nFROM ")[1:]

    assert "AS engine-download" in builder
    assert "ARG REDOT_VERSION=26.3-stable" in builder
    assert "ARG REDOT_SHA512=" in builder
    assert "sha512sum -c" in builder
    assert "grep -Fxc 'redot.linuxbsd.editor.x86_64'" in builder
    assert "-eq 1" in builder
    assert "unzip -p /tmp/redot.zip redot.linuxbsd.editor.x86_64" in builder
    assert "head -n" not in builder
    assert "curl" not in final
    assert "unzip" not in final
    assert "COPY --from=engine-download /opt/redot /opt/redot" in final
