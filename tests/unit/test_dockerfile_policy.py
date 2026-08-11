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
