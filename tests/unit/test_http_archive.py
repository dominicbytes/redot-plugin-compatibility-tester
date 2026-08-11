from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import pytest

from redot_compat.errors import SourceResolutionError
from redot_compat.sources.http_archive import HttpArchiveSource, download_http_archive


def _zip_bytes() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("addons/example/plugin.cfg", "[plugin]\nname='Example'\n")
    return output.getvalue()


def test_download_streams_and_hashes_https_archive(tmp_path: Path) -> None:
    data = _zip_bytes()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "application/zip", "etag": '"abc"'},
            content=data,
            request=request,
        )
    )
    client = httpx.Client(transport=transport)

    artifact = download_http_archive(
        "https://example.test/plugin.zip", tmp_path / "plugin.zip", client=client
    )

    assert artifact.size == len(data)
    assert artifact.sha256
    assert artifact.etag == '"abc"'


def test_rejects_http_and_cross_host_redirects(tmp_path: Path) -> None:
    with pytest.raises(SourceResolutionError, match="HTTPS"):
        download_http_archive("http://example.test/plugin.zip", tmp_path / "http.zip")

    def redirect(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.test":
            return httpx.Response(302, headers={"location": "https://other.test/plugin.zip"})
        return httpx.Response(200, content=_zip_bytes())

    client = httpx.Client(transport=httpx.MockTransport(redirect))
    with pytest.raises(SourceResolutionError, match="redirect host"):
        download_http_archive(
            "https://example.test/plugin.zip", tmp_path / "redirect.zip", client=client
        )

    assert not (tmp_path / "redirect.zip").exists()


def test_http_source_extracts_into_owned_run_directory(tmp_path: Path) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "application/zip"},
            content=_zip_bytes(),
            request=request,
        )
    )
    source = HttpArchiveSource(client=httpx.Client(transport=transport))

    resolved = source.acquire("https://example.test/plugin.zip", tmp_path / "run")

    assert resolved.provenance.source_kind.value == "http_archive"
    assert (resolved.content_root / "addons/example/plugin.cfg").exists()
