from __future__ import annotations

from redot_compat.sandbox.base import Backend, select_backend


def test_auto_prefers_eligible_docker() -> None:
    selected = select_backend(
        "auto", docker_eligible=True, trusted_source=False, allow_unsafe_host=False
    )

    assert selected.backend is Backend.DOCKER_LINUX


def test_host_requires_trust_and_explicit_consent() -> None:
    denied = select_backend(
        "host", docker_eligible=False, trusted_source=True, allow_unsafe_host=False
    )
    allowed = select_backend(
        "host", docker_eligible=False, trusted_source=True, allow_unsafe_host=True
    )

    assert denied.backend is Backend.NONE
    assert "explicit" in denied.reason
    assert allowed.backend is Backend.TRUSTED_HOST


def test_auto_does_not_fall_back_to_host_silently() -> None:
    selected = select_backend(
        "auto", docker_eligible=False, trusted_source=True, allow_unsafe_host=True
    )

    assert selected.backend is Backend.NONE
    assert "does not silently" in selected.reason
