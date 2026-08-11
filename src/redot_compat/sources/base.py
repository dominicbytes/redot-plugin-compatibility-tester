from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from redot_compat.models import SourceProvenance


@dataclass(frozen=True, slots=True)
class ResolvedArtifact:
    provenance: SourceProvenance
    content_root: Path
    content_sha256: str
    input_path: Path
    provider_capabilities: dict[str, str] = field(default_factory=dict)


class SourceAdapter(Protocol):
    def acquire(
        self,
        source: str,
        run_dir: Path,
        *,
        requested_ref: str | None = None,
    ) -> ResolvedArtifact: ...
