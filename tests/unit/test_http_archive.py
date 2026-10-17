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


class _Chunks(httpx.SyncByteStream):
    def __iter__(self):  # type: ignore[no-untyped-def]
        yield b"abc"
        yield b"def"


@pytest.mark.parametrize("length", [None, "100"])
def test_download_size_caps(tmp_path: Path, length: str | None) -> None:
    headers = {} if length is None else {"Content-Length": length}
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, headers=headers, stream=_Chunks())
        )
    )
    with pytest.raises(SourceResolutionError, match="exceeds 4 bytes"):
        download_http_archive("https://example.test/a", tmp_path / "a", client=client, max_bytes=4)
    assert not (tmp_path / "a").exists()
    assert not (tmp_path / ".a.partial").exists()


@pytest.mark.parametrize(
    "location, message",
    [
        ("http://example.test/a", "HTTPS"),
        ("https://example.test:123/a", "port"),
        ("/again", "redirects"),
    ],
)
def test_redirect_policy(tmp_path: Path, location: str, message: str) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(302, headers={"location": location})

    client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    with pytest.raises(SourceResolutionError, match=message):
        download_http_archive(
            "https://example.test/a", tmp_path / "a", client=client, max_redirects=1
        )
    assert len(requests) <= 2


@pytest.mark.parametrize("hosts", [set(), {"other.test"}])
def test_initial_host_allowlist(tmp_path: Path, hosts: set[str]) -> None:
    with pytest.raises(SourceResolutionError, match="host is not allowed"):
        download_http_archive("https://example.test/a", tmp_path / "a", allowed_hosts=hosts)


@pytest.mark.parametrize("port", [443, 8443])
def test_redirect_accepts_original_or_default_port(tmp_path: Path, port: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/a":
            return httpx.Response(302, headers={"location": f"https://EXAMPLE.test:{port}/b"})
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(200, content=_zip_bytes())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    download_http_archive(
        "https://example.test:8443/a",
        tmp_path / "a",
        client=client,
        headers={"authorization": "Bearer secret"},
    )


def test_cross_host_strips_authorization_including_client_defaults(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.test":
            assert request.headers["Authorization"] == "Bearer secret"
            return httpx.Response(302, headers={"location": "https://other.test/a"})
        assert "authorization" not in request.headers
        return httpx.Response(200, content=_zip_bytes())

    client = httpx.Client(
        transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer client-secret"}
    )
    download_http_archive(
        "https://example.test/a",
        tmp_path / "a",
        client=client,
        headers={"aUtHoRiZaTiOn": "Bearer secret"},
        allowed_hosts={"EXAMPLE.test", "other.test"},
    )


def test_download_deadline_checked_while_streaming(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from redot_compat.sources import http_archive

    now = [0.0]

    class SlowChunks(httpx.SyncByteStream):
        def __iter__(self):  # type: ignore[no-untyped-def]
            yield b"abc"
            now[0] = 11.0
            yield b"def"

    monkeypatch.setattr(http_archive.time, "monotonic", lambda: now[0])
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=SlowChunks()))
    )
    with pytest.raises(SourceResolutionError, match="deadline"):
        download_http_archive(
            "https://example.test/a", tmp_path / "a", client=client, deadline_seconds=10
        )
    assert not (tmp_path / ".a.partial").exists()


def test_download_wraps_stream_http_error_without_exposing_secrets(tmp_path: Path) -> None:
    class BrokenChunks(httpx.SyncByteStream):
        def __iter__(self):  # type: ignore[no-untyped-def]
            yield b"abc"
            raise httpx.ReadError("secret-token")

    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=BrokenChunks()))
    )
    with pytest.raises(SourceResolutionError, match="ReadError") as caught:
        download_http_archive("https://example.test/a", tmp_path / "a", client=client)
    assert "secret-token" not in str(caught.value)


def test_second_redirect_hop_cannot_downgrade(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        location = "/second" if request.url.path == "/first" else "http://example.test/third"
        return httpx.Response(302, headers={"location": location})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(SourceResolutionError, match="HTTPS"):
        download_http_archive("https://example.test/first", tmp_path / "a", client=client)


def test_request_http_error_is_wrapped(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret-token", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(SourceResolutionError, match="ConnectError") as caught:
        download_http_archive("https://example.test/a", tmp_path / "a", client=client)
    assert "secret-token" not in str(caught.value)


def test_http_source_owned_close_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    source = HttpArchiveSource()

    def fail() -> None:
        raise httpx.CloseError("secret-token")

    monkeypatch.setattr(source._client, "close", fail)
    with pytest.raises(SourceResolutionError, match="close") as caught:
        source.close()
    assert "secret-token" not in str(caught.value)


@pytest.mark.parametrize("quota", ["download", "extraction"])
def test_source_enforces_custom_archive_limits(tmp_path: Path, quota: str) -> None:
    from redot_compat.config import ArchiveLimits
    from redot_compat.errors import UnsafeArchiveError

    limits = (
        ArchiveLimits(max_archive_bytes=1)
        if quota == "download"
        else ArchiveLimits(max_file_bytes=1)
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/version"):
            return httpx.Response(200, json={"version": "1"})
        if "/commits/" in request.url.path:
            return httpx.Response(200, json={"sha": "a" * 40})
        return httpx.Response(200, content=_zip_bytes())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = HttpArchiveSource(client=client)
    url = "https://example.test/plugin.zip"
    with pytest.raises((SourceResolutionError, UnsafeArchiveError)):
        source.acquire(url, tmp_path / "limited", limits=limits)
    assert not (tmp_path / "limited/source").exists()
