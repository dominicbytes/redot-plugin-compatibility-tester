"""Immutable source acquisition adapters."""

from redot_compat.sources.base import ResolvedArtifact
from redot_compat.sources.local import acquire_local_source

__all__ = ["ResolvedArtifact", "acquire_local_source"]
