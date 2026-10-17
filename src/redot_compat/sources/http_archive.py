from __future__ import annotations

import hashlib
import os
import tarfile
import time
import zipfile
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from redot_compat.archive.extract import extract_archive
from redot_compat.config import ArchiveLimits
from redot_compat.errors import SourceResolutionError
from redot_compat.models import SourceKind, SourceProvenance
from redot_compat.sources.base import ResolvedArtifact


@dataclass(frozen=True, slots=True)
class DownloadArtifact:
    path: Path
    sha256: str
    size: int
    final_url: str
    redirects: list[str]
    content_type: str | None
    etag: str | None


class HttpArchiveSource:
    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=httpx.Timeout(30.0, read=120.0))

    def acquire(
        self,
        source: str,
        run_dir: Path,
        *,
        requested_ref: str | None = None,
        limits: ArchiveLimits | None = None,
    ) -> ResolvedArtifact:
        limits = limits or ArchiveLimits()
        if requested_ref is not None:
            raise SourceResolutionError("direct archives do not accept --ref")
        parsed = urlsplit(source)
        name = Path(parsed.path).name or "source.archive"
        input_path = run_dir / "input" / name
        download = download_http_archive(
            source, input_path, client=self._client, max_bytes=limits.max_archive_bytes
        )
        content_root = run_dir / "source"
        extract_archive(input_path, content_root, limits=limits)
        provenance = SourceProvenance(
            source_kind=SourceKind.HTTP_ARCHIVE,
            requested_url_or_path=source,
            canonical_url=download.final_url,
            host=parsed.hostname,
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
            provider_capabilities={"immutable_identity": "sha256"},
        )

    def close(self) -> None:
        if self._owns_client:
            _close_client(self._client)


_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_HTTPS_DEFAULT_PORT = 443
DEFAULT_DOWNLOAD_DEADLINE_SECONDS = 600.0


def download_http_archive(
    url: str,
    destination: Path,
    *,
    client: httpx.Client | None = None,
    max_bytes: int = 512 * 1024 * 1024,
    max_redirects: int = 5,
    allowed_hosts: set[str] | None = None,
    headers: dict[str, str] | None = None,
    deadline_seconds: float = DEFAULT_DOWNLOAD_DEADLINE_SECONDS,
) -> DownloadArtifact:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise SourceResolutionError("direct archive acquisition requires an HTTPS URL")
    original_host = parsed.hostname.casefold()
    try:
        original_port = _url_port(url)
    except ValueError as exc:
        raise SourceResolutionError(f"archive URL has an invalid port: {exc}") from exc
    allowed = {
        host.casefold()
        for host in (allowed_hosts if allowed_hosts is not None else {original_host})
    }
    if original_host not in allowed:
        raise SourceResolutionError(f"archive host is not allowed: {parsed.hostname}")
    if destination.exists():
        raise SourceResolutionError(f"download destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.partial")
    deadline = time.monotonic() + deadline_seconds
    redirects: list[str] = []
    current = url
    request_headers = dict(headers or {})
    owns_client = client is None
    active_client = client or httpx.Client(timeout=httpx.Timeout(30.0, read=120.0))
    try:
        for _ in range(max_redirects + 1):
            _check_deadline(deadline, deadline_seconds)
            request = active_client.build_request("GET", current, headers=request_headers)
            cross_host = urlsplit(current).hostname != original_host
            if cross_host:
                request.headers.pop("Authorization", None)
            response = (
                active_client.send(request, stream=True, follow_redirects=False, auth=None)
                if cross_host
                else active_client.send(request, stream=True, follow_redirects=False)
            )
            with closing(response):
                if response.status_code in _REDIRECT_STATUSES:
                    current = _next_hop(
                        current, response, allowed=allowed, original_port=original_port
                    )
                    if urlsplit(current).hostname != original_host:
                        request_headers = _without_authorization(request_headers)
                    redirects.append(current)
                    continue
                if response.status_code != 200:
                    raise SourceResolutionError(
                        f"archive request returned HTTP {response.status_code}"
                    )
                length = response.headers.get("content-length")
                if length and int(length) > max_bytes:
                    raise SourceResolutionError(f"archive exceeds {max_bytes} bytes")
                digest = hashlib.sha256()
                size = 0
                with partial.open("xb") as writer:
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            raise SourceResolutionError(f"archive exceeds {max_bytes} bytes")
                        _check_deadline(deadline, deadline_seconds)
                        digest.update(chunk)
                        writer.write(chunk)
                _check_deadline(deadline, deadline_seconds)
                if not (zipfile.is_zipfile(partial) or tarfile.is_tarfile(partial)):
                    raise SourceResolutionError("download is not a supported ZIP or TAR archive")
                os.replace(partial, destination)
                return DownloadArtifact(
                    path=destination,
                    sha256=digest.hexdigest(),
                    size=size,
                    final_url=current,
                    redirects=redirects,
                    content_type=response.headers.get("content-type"),
                    etag=response.headers.get("etag"),
                )
        raise SourceResolutionError(f"archive request exceeded {max_redirects} redirects")
    except httpx.HTTPError as exc:
        raise SourceResolutionError(f"archive download failed ({type(exc).__name__})") from exc
    except (OSError, ValueError) as exc:
        raise SourceResolutionError(f"archive download failed: {exc}") from exc
    finally:
        partial.unlink(missing_ok=True)
        if owns_client:
            _close_client(active_client)


def _next_hop(
    current: str, response: httpx.Response, *, allowed: set[str], original_port: int
) -> str:
    location = response.headers.get("location")
    if not location:
        raise SourceResolutionError("redirect response did not include Location")
    next_url: str = urljoin(current, location)
    parsed = urlsplit(next_url)
    if parsed.scheme.lower() != "https":
        raise SourceResolutionError(
            f"redirect must stay on HTTPS, refusing {parsed.scheme or '<missing>'}"
        )
    next_host = parsed.hostname
    if not next_host or next_host.casefold() not in allowed:
        raise SourceResolutionError(f"redirect host is not allowed: {next_host or '<missing>'}")
    next_port = _url_port(next_url)
    if next_port not in {_HTTPS_DEFAULT_PORT, original_port}:
        raise SourceResolutionError(f"redirect port is not allowed: {next_port}")
    return next_url


def _url_port(url: str) -> int:
    port = urlsplit(url).port
    return _HTTPS_DEFAULT_PORT if port is None else port


def _without_authorization(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key.casefold() != "authorization"}


def _check_deadline(deadline: float, deadline_seconds: float) -> None:
    if time.monotonic() > deadline:
        raise SourceResolutionError(f"archive download exceeded {deadline_seconds:g}s deadline")


def _close_client(client: httpx.Client) -> None:
    try:
        client.close()
    except httpx.HTTPError as exc:
        raise SourceResolutionError("could not close archive HTTP client") from exc
