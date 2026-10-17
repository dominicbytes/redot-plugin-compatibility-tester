"""Shared acquisition flow for Git forges (GitHub, Codeberg/Gitea)."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from fnmatch import fnmatchcase
from hmac import compare_digest
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import quote, urlsplit

import httpx

from redot_compat.archive.extract import extract_archive
from redot_compat.config import ArchiveLimits
from redot_compat.errors import SourceResolutionError
from redot_compat.models import SourceKind, SourceProvenance
from redot_compat.sources.base import ResolvedArtifact
from redot_compat.sources.http_archive import download_http_archive

_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")
_NAME = re.compile(r"^[A-Za-z0-9._-]+$")
_RATE_LIMIT_STATUSES = frozenset({403, 429})


@dataclass(frozen=True, slots=True)
class ForgeSpec:
    """Host-specific parameters for one forge API."""

    name: str
    web_host: str
    source_kind: SourceKind
    api_root: str
    commit_path: str
    default_ref: str
    auth_scheme: str
    token_env: str
    base_headers: Mapping[str, str]
    download_hosts: frozenset[str]
    default_archive_name: str
    asset_kind: str
    asset_noun: str


@dataclass(frozen=True, slots=True)
class _ResolvedRef:
    requested: str
    commit: str
    release_body: dict[str, Any] | None


class ForgeSource:
    """Resolves a forge repository ref to a commit and downloads its archive."""

    spec: ClassVar[ForgeSpec]

    def __init__(self, *, client: httpx.Client | None = None, token: str | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=httpx.Timeout(30.0, read=120.0))
        self._headers: dict[str, str] = dict(self.spec.base_headers)
        resolved_token = token if token is not None else os.environ.get(self.spec.token_env)
        self._authenticated = bool(resolved_token and resolved_token.strip())
        if resolved_token and self._authenticated:
            self._headers["Authorization"] = f"{self.spec.auth_scheme} {resolved_token.strip()}"

    def acquire(
        self,
        source: str,
        run_dir: Path,
        *,
        requested_ref: str | None = None,
        limits: ArchiveLimits | None = None,
        release: str | None = None,
        asset_pattern: str | None = None,
    ) -> ResolvedArtifact:
        limits = limits or ArchiveLimits()
        owner, repository = parse_repository(source, self.spec)
        if release is not None and requested_ref is not None:
            raise SourceResolutionError("choose --ref or --release, not both")
        if asset_pattern is not None and release is None:
            raise SourceResolutionError("--asset requires --release")
        capabilities = self._base_capabilities()
        api = f"{self.spec.api_root}/repos/{owner}/{repository}"
        resolved = self._resolve_ref(api, requested_ref=requested_ref, release=release)

        selected_asset: dict[str, Any] | None = None
        download_url = self._commit_archive_url(owner, repository, api, resolved.commit)
        if asset_pattern is not None and resolved.release_body is not None:
            selected_asset = select_asset(resolved.release_body, asset_pattern)
            download_url = str(selected_asset.get("browser_download_url") or "")
            if not download_url:
                raise SourceResolutionError(
                    f"{self.spec.name} {self.spec.asset_noun} has no download URL"
                )
        suffix = Path(urlsplit(download_url).path).name or self.spec.default_archive_name
        input_path = run_dir / "input" / suffix
        download = download_http_archive(
            download_url,
            input_path,
            client=self._client,
            max_bytes=limits.max_archive_bytes,
            allowed_hosts=set(self.spec.download_hosts),
            headers=self._headers,
        )
        published_digest = self._verify_published_digest(selected_asset, download.sha256)
        content_root = run_dir / "source"
        extract_archive(input_path, content_root, limits=limits)
        release_body = resolved.release_body
        provenance = SourceProvenance(
            source_kind=self.spec.source_kind,
            requested_url_or_path=source,
            canonical_url=f"https://{self.spec.web_host}/{owner}/{repository}",
            host=self.spec.web_host,
            owner=owner,
            repository=repository,
            requested_ref=resolved.requested,
            resolved_ref=resolved.requested,
            resolved_commit=resolved.commit.lower(),
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
        capabilities["artifact_kind"] = (
            self.spec.asset_kind if selected_asset is not None else "commit_archive"
        )
        return ResolvedArtifact(
            provenance=provenance,
            content_root=content_root,
            content_sha256=download.sha256,
            input_path=input_path,
            provider_capabilities=capabilities,
        )

    def close(self) -> None:
        if self._owns_client:
            try:
                self._client.close()
            except httpx.HTTPError as exc:
                raise SourceResolutionError("could not close forge HTTP client") from exc

    def _base_capabilities(self) -> dict[str, str]:
        return {}

    def _commit_archive_url(self, owner: str, repository: str, api: str, commit: str) -> str:
        raise NotImplementedError

    def _resolve_ref(
        self, api: str, *, requested_ref: str | None, release: str | None
    ) -> _ResolvedRef:
        name = self.spec.name
        release_body: dict[str, Any] | None = None
        if release is not None:
            endpoint = "latest" if release == "latest" else f"tags/{quote(release, safe='')}"
            release_response = self._get(f"{api}/releases/{endpoint}")
            if release_response.status_code != 200:
                raise SourceResolutionError(
                    f"{name} could not resolve release {release!r}: "
                    f"HTTP {release_response.status_code}"
                )
            release_body = self._json_object(release_response, "release")
            requested = str(release_body.get("tag_name") or "")
            if not requested:
                raise SourceResolutionError(f"{name} release did not include a tag name")
        else:
            requested = requested_ref or self.spec.default_ref
        commit_response = self._get(f"{api}/{self.spec.commit_path}/{quote(requested, safe='')}")
        if commit_response.status_code != 200:
            raise SourceResolutionError(
                f"{name} could not resolve ref {requested!r}: HTTP {commit_response.status_code}"
            )
        body = self._json_object(commit_response, "commit")
        commit = str(body.get("sha") or body.get("id") or "")
        if not _COMMIT.fullmatch(commit):
            raise SourceResolutionError(f"{name} returned an invalid commit identity")
        return _ResolvedRef(requested=requested, commit=commit, release_body=release_body)

    def _verify_published_digest(self, asset: dict[str, Any] | None, sha256: str) -> str | None:
        if asset is None or not asset.get("digest"):
            return None
        published_digest = str(asset["digest"])
        algorithm, separator, expected = published_digest.partition(":")
        if (
            algorithm.casefold() != "sha256"
            or not separator
            or not compare_digest(expected.casefold(), sha256.casefold())
        ):
            raise SourceResolutionError(
                f"{self.spec.name} published asset digest did not match bytes"
            )
        return published_digest

    def _get(self, url: str) -> httpx.Response:
        try:
            response = self._client.get(url, headers=self._headers, follow_redirects=False)
        except httpx.HTTPError as exc:
            raise SourceResolutionError(
                f"{self.spec.name} API request failed ({type(exc).__name__})"
            ) from exc
        self._raise_for_rate_limit(response)
        return response

    def _raise_for_rate_limit(self, response: httpx.Response) -> None:
        if response.status_code not in _RATE_LIMIT_STATUSES:
            return
        headers = response.headers
        if not (
            headers.get("x-ratelimit-remaining") == "0"
            or "retry-after" in headers
            or response.status_code == 429
        ):
            return
        if self._authenticated:
            raise SourceResolutionError(
                f"{self.spec.name} API rate limit was hit for the configured token "
                f"(HTTP {response.status_code}); retry after the limit resets"
            )
        raise SourceResolutionError(
            f"{self.spec.name} anonymous API rate limit was hit "
            f"(HTTP {response.status_code}); set {self.spec.token_env} to authenticate"
        )

    def _json_object(self, response: httpx.Response, what: str) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise SourceResolutionError(
                f"{self.spec.name} returned invalid JSON for the {what}"
            ) from exc
        if not isinstance(body, dict):
            raise SourceResolutionError(f"{self.spec.name} returned a non-object {what} response")
        return body


def parse_repository(source: str, spec: ForgeSpec) -> tuple[str, str]:
    parsed = urlsplit(source)
    if parsed.scheme != "https" or parsed.hostname != spec.web_host:
        raise SourceResolutionError(
            f"{spec.name} source must be an https://{spec.web_host}/owner/repo URL"
        )
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise SourceResolutionError(
            f"{spec.name} repository URL must contain exactly owner/repository"
        )
    owner, repository = parts[0], parts[1].removesuffix(".git")
    for value in (owner, repository):
        if not _NAME.fullmatch(value) or value in {".", ".."}:
            raise SourceResolutionError(
                f"{spec.name} repository URL has an invalid owner or repository name"
            )
    return owner, repository


def select_asset(release: dict[str, Any], pattern: str) -> dict[str, Any]:
    raw_assets = release.get("assets")
    assets = [
        item
        for item in (raw_assets if isinstance(raw_assets, list) else [])
        if isinstance(item, dict) and fnmatchcase(str(item.get("name", "")), pattern)
    ]
    if len(assets) != 1:
        raise SourceResolutionError(
            f"release asset pattern {pattern!r} matched {len(assets)} assets; expected one"
        )
    return assets[0]
