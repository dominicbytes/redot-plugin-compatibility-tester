from __future__ import annotations

import re
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from hmac import compare_digest
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


class GitHubSource:
    def __init__(self, *, client: httpx.Client | None = None, token: str | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=httpx.Timeout(30.0, read=120.0))
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

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
        api = f"https://api.github.com/repos/{owner}/{repository}"
        release_body: dict[str, Any] | None = None
        if release is not None:
            if requested_ref is not None:
                raise SourceResolutionError("choose --ref or --release, not both")
            endpoint = "latest" if release == "latest" else f"tags/{release}"
            release_response = self._client.get(
                f"{api}/releases/{endpoint}", headers=self._headers, follow_redirects=False
            )
            if release_response.status_code != 200:
                raise SourceResolutionError(
                    f"GitHub could not resolve release {release!r}: "
                    f"HTTP {release_response.status_code}"
                )
            release_body = release_response.json()
            requested = str(release_body.get("tag_name") or "")
            if not requested:
                raise SourceResolutionError("GitHub release did not include a tag name")
        else:
            requested = requested_ref or "HEAD"
        response = self._client.get(
            f"{api}/commits/{requested}", headers=self._headers, follow_redirects=False
        )
        if response.status_code != 200:
            raise SourceResolutionError(
                f"GitHub could not resolve ref {requested!r}: HTTP {response.status_code}"
            )
        commit = str(response.json().get("sha", ""))
        if not _COMMIT.fullmatch(commit):
            raise SourceResolutionError("GitHub returned an invalid commit identity")

        selected_asset: dict[str, Any] | None = None
        download_url = f"{api}/zipball/{commit}"
        if asset_pattern is not None:
            if release_body is None:
                raise SourceResolutionError("--asset requires --release")
            selected_asset = _select_asset(release_body, asset_pattern)
            download_url = str(selected_asset.get("browser_download_url") or "")
            if not download_url:
                raise SourceResolutionError("GitHub release asset has no download URL")
        suffix = Path(urlsplit(download_url).path).name or "source.zip"
        input_path = run_dir / "input" / suffix
        download = download_http_archive(
            download_url,
            input_path,
            client=self._client,
            allowed_hosts={
                "api.github.com",
                "github.com",
                "codeload.github.com",
                "objects.githubusercontent.com",
            },
            headers=self._headers,
        )
        published_digest = None
        if selected_asset is not None and selected_asset.get("digest"):
            published_digest = str(selected_asset["digest"])
            algorithm, separator, expected = published_digest.partition(":")
            if (
                algorithm.casefold() != "sha256"
                or not separator
                or not compare_digest(expected.casefold(), download.sha256.casefold())
            ):
                raise SourceResolutionError("GitHub published asset digest did not match bytes")
        content_root = run_dir / "source"
        extract_archive(input_path, content_root)
        provenance = SourceProvenance(
            source_kind=SourceKind.GITHUB,
            requested_url_or_path=source,
            canonical_url=f"https://github.com/{owner}/{repository}",
            host="github.com",
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
            published_digest=published_digest,
        )
        return ResolvedArtifact(
            provenance=provenance,
            content_root=content_root,
            content_sha256=download.sha256,
            input_path=input_path,
            provider_capabilities={
                "api": "GitHub REST 2022-11-28",
                "artifact_kind": "release_asset" if selected_asset else "commit_archive",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def _parse_repository(source: str) -> tuple[str, str]:
    parsed = urlsplit(source)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise SourceResolutionError("GitHub source must be an https://github.com/owner/repo URL")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise SourceResolutionError("GitHub repository URL must contain exactly owner/repository")
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
