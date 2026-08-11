from __future__ import annotations

from enum import StrEnum

from redot_compat.models.base import ContractModel


class Backend(StrEnum):
    NONE = "none"
    DOCKER_LINUX = "docker_linux"
    TRUSTED_HOST = "trusted_host"


class BackendSelection(ContractModel):
    backend: Backend
    reason: str


def select_backend(
    requested: str,
    *,
    docker_eligible: bool,
    trusted_source: bool,
    allow_unsafe_host: bool,
) -> BackendSelection:
    normalized = requested.casefold()
    if normalized not in {"auto", "docker", "host"}:
        raise ValueError("backend must be auto, docker, or host")
    if normalized == "auto":
        if docker_eligible:
            return BackendSelection(
                backend=Backend.DOCKER_LINUX,
                reason="eligible Docker backend selected",
            )
        return BackendSelection(
            backend=Backend.NONE,
            reason="auto does not silently fall back to unsafe host execution",
        )
    if normalized == "docker":
        if docker_eligible:
            return BackendSelection(
                backend=Backend.DOCKER_LINUX,
                reason="requested Docker backend is eligible",
            )
        return BackendSelection(
            backend=Backend.NONE,
            reason="Docker daemon or verified worker image is unavailable",
        )
    if not trusted_source:
        return BackendSelection(
            backend=Backend.NONE,
            reason="host execution is limited to an explicitly trusted source",
        )
    if not allow_unsafe_host:
        return BackendSelection(
            backend=Backend.NONE,
            reason="host execution requires explicit --allow-unsafe-host-execution consent",
        )
    return BackendSelection(
        backend=Backend.TRUSTED_HOST,
        reason="operator explicitly consented to trusted host execution",
    )
