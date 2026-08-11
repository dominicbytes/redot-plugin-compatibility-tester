from __future__ import annotations

from datetime import datetime

from pydantic import Field

from redot_compat.models.base import ContractModel
from redot_compat.models.enums import SourceKind


class SourceProvenance(ContractModel):
    source_kind: SourceKind
    requested_url_or_path: str
    canonical_url: str
    host: str | None = None
    owner: str | None = None
    repository: str | None = None
    requested_ref: str | None = None
    resolved_ref: str | None = None
    resolved_commit: str | None = None
    release_id: str | None = None
    release_tag: str | None = None
    release_asset_name: str | None = None
    download_url: str | None = None
    redirects: list[str] = Field(default_factory=list)
    retrieved_at: datetime
    archive_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    archive_size: int = Field(ge=0)
    http_etag: str | None = None
    content_type: str | None = None
    published_digest: str | None = None
    license_candidates: list[str] = Field(default_factory=list)
