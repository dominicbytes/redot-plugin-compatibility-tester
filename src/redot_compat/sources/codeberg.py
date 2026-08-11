from __future__ import annotations

import re
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from redot_compat.archive.extract import extract_archive
from redot_compat.errors import SourceResolutionError
from redot_compat.models import SourceKind, SourceProvenance
from redot_compat.sources.base import ResolvedArtifact
from redot_compat.sources.http_archive import download_http_archive

_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")


class CodebergSource:
    def __init__(self, *, client: httpx.Client | None = None, token: str | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=httpx.Timeout(30.0, read=120.0))
        self._headers: dict[str, str] = {"Accept": "application/json"}
        if token:
            self._headers["Authorization"] = f"token {token}"

    def acquire(
        self,
        source: str,
        run_dir: Path,
        *,
        requested_ref: str | None = None,
        release: str | None = None,
        asset_pattern: str | None = None,
    ) -> ResolvedArtifact:
        owner, repository = _parse_repository(source)
        version_response = self._client.get(
            "https://codeberg.org/api/v1/version", headers=self._headers
        )
        version = "unknown"
        if version_response.status_code == 200:
            version = str(version_response.json().get("version", "unknown"))
        release_body: dict[str, Any] | None = None
        if release is not None:
            if requested_ref is not None:
                raise SourceResolutionError("choose --ref or --release, not both")
            endpoint = "latest" if release == "latest" else f"tags/{release}"
            release_response = self._client.get(
                f"https://codeberg.org/api/v1/repos/{owner}/{repository}/releases/{endpoint}",
                headers=self._headers,
            )
            if release_response.status_code != 200:
                raise SourceResolutionError(
                    f"Codeberg could not resolve release {release!r}: "
                    f"HTTP {release_response.status_code}"
                )
            release_body = release_response.json()
            requested = str(release_body.get("tag_name") or "")
            if not requested:
                raise SourceResolutionError("Codeberg release did not include a tag name")
        else:
            requested = requested_ref or "main"
        commit_response = self._client.get(
            f"https://codeberg.org/api/v1/repos/{owner}/{repository}/git/commits/{requested}",
            headers=self._headers,
        )
        if commit_response.status_code != 200:
            raise SourceResolutionError(
                f"Codeberg could not resolve ref {requested!r}: HTTP {commit_response.status_code}"
            )
        body = commit_response.json()
        commit = str(body.get("sha") or body.get("id") or "")
        if not _COMMIT.fullmatch(commit):
            raise SourceResolutionError("Codeberg returned an invalid commit identity")

        selected_asset: dict[str, Any] | None = None
        download_url = f"https://codeberg.org/{owner}/{repository}/archive/{commit}.tar.gz"
        if asset_pattern is not None:
            if release_body is None:
                raise SourceResolutionError("--asset requires --release")
            selected_asset = _select_asset(release_body, asset_pattern)
            download_url = str(selected_asset.get("browser_download_url") or "")
            if not download_url:
                raise SourceResolutionError("Codeberg attachment has no download URL")
        suffix = Path(urlsplit(download_url).path).name or "source.tar.gz"
        input_path = run_dir / "input" / suffix
        download = download_http_archive(
            download_url,
            input_path,
            client=self._client,
            allowed_hosts={"codeberg.org"},
            headers=self._headers,
        )
        content_root = run_dir / "source"
        extract_archive(input_path, content_root)
        provenance = SourceProvenance(
            source_kind=SourceKind.CODEBERG,
            requested_url_or_path=source,
            canonical_url=f"https://codeberg.org/{owner}/{repository}",
            host="codeberg.org",
            owner=owner,
            repository=repository,
            requested_ref=requested,
            resolved_ref=requested,
            resolved_commit=commit.lower(),
            release_id=(str(release_body.get("id")) if release_body is not None else None),
            release_tag=(str(release_body.get("tag_name")) if release_body is not None else None),
            release_asset_name=(
                str(selected_asset.get("name")) if selected_asset is not None else None
            ),
            download_url=download.final_url,
            redirects=download.redirects,
            retrieved_at=datetime.now(UTC),
            archive_sha256=download.sha256,
            archive_size=download.size,
            http_etag=download.etag,
            content_type=download.content_type,
        )
        return ResolvedArtifact(
            provenance=provenance,
            content_root=content_root,
            content_sha256=download.sha256,
            input_path=input_path,
            provider_capabilities={
                "version": version,
                "archive_by_commit": "true",
                "artifact_kind": "release_attachment" if selected_asset else "commit_archive",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def _parse_repository(source: str) -> tuple[str, str]:
    parsed = urlsplit(source)
    if parsed.scheme != "https" or parsed.hostname != "codeberg.org":
        raise SourceResolutionError(
            "Codeberg source must be an https://codeberg.org/owner/repo URL"
        )
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise SourceResolutionError("Codeberg repository URL must contain exactly owner/repository")
    return parts[0], parts[1].removesuffix(".git")


def _select_asset(release: dict[str, Any], pattern: str) -> dict[str, Any]:
    assets = [
        item
        for item in release.get("assets", [])
        if isinstance(item, dict) and fnmatchcase(str(item.get("name", "")), pattern)
    ]
    if len(assets) != 1:
        raise SourceResolutionError(
            f"release asset pattern {pattern!r} matched {len(assets)} assets; expected one"
        )
    return assets[0]
