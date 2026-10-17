from __future__ import annotations

# Redot release line -> Godot lineage it is built on. Each entry is verified against the
# ``header`` of ``--dump-extension-api`` output from the official stable build.
REDOT_GODOT_LINEAGE: dict[str, str] = {
    "26.2": "4.5.2",
    "26.3": "4.5.2",
}


def redot_release_line(version: str) -> str:
    """Return the ``major.minor`` release line of a Redot version string."""

    return ".".join(version.split(".")[:2])


def godot_lineage_for_redot(version: str) -> str | None:
    """Return the known Godot lineage for a Redot version, or ``None`` if unknown."""

    return REDOT_GODOT_LINEAGE.get(redot_release_line(version))
