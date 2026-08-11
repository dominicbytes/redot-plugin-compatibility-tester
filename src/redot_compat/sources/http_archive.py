from __future__ import annotations

import hashlib
import os
import tarfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from redot_compat.archive.extract import extract_archive
from redot_compat.archive.hash import CHUNK_SIZE
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
    ) -> ResolvedArtifact:
        if requested_ref is not None:
            raise SourceResolutionError("direct archives do not accept --ref")
        parsed = urlsplit(source)
        name = Path(parsed.path).name or "source.archive"
        input_path = run_dir / "input" / name
        download = download_http_archive(source, input_path, client=self._client)
        content_root = run_dir / "source"
        extract_archive(input_path, content_root)
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
            self._client.close()


def download_http_archive(
    url: str,
    destination: Path,
    *,
    client: httpx.Client | None = None,
    max_bytes: int = 512 * 1024 * 1024,
    max_redirects: int = 5,
    allowed_hosts: set[str] | None = None,
    headers: dict[str, str] | None = None,
) -> DownloadArtifact:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise SourceResolutionError("direct archive acquisition requires an HTTPS URL")
    if destination.exists():
        raise SourceResolutionError(f"download destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f".{destination.name}.partial")
    allowed = {host.casefold() for host in (allowed_hosts or {parsed.hostname})}
    redirects: list[str] = []
    current = url
    owns_client = client is None
    active_client = client or httpx.Client(timeout=httpx.Timeout(30.0, read=120.0))
    try:
        for _ in range(max_redirects + 1):
            with active_client.stream(
                "GET", current, headers=headers, follow_redirects=False
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise SourceResolutionError("redirect response did not include Location")
                    next_url = urljoin(current, location)
                    next_host = urlsplit(next_url).hostname
                    if not next_host or next_host.casefold() not in allowed:
                        raise SourceResolutionError(
                            f"redirect host is not allowed: {next_host or '<missing>'}"
                        )
                    redirects.append(next_url)
                    current = next_url
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
                    for chunk in response.iter_bytes(CHUNK_SIZE):
                        size += len(chunk)
                        if size > max_bytes:
                            raise SourceResolutionError(f"archive exceeds {max_bytes} bytes")
                        digest.update(chunk)
                        writer.write(chunk)
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
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise SourceResolutionError(f"archive download failed: {exc}") from exc
    finally:
        partial.unlink(missing_ok=True)
        if owns_client:
            active_client.close()
