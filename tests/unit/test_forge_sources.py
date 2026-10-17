from __future__ import annotations

import io
import zipfile
from pathlib import Path
from urllib.parse import quote

import httpx
import pytest

from redot_compat.errors import SourceResolutionError
from redot_compat.sources.codeberg import CodebergSource
from redot_compat.sources.github import GitHubSource


@pytest.fixture(params=[GitHubSource, CodebergSource])
def provider(request: pytest.FixtureRequest) -> type[GitHubSource] | type[CodebergSource]:
    return request.param  # type: ignore[no-any-return]


def _zip() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("plugin.cfg", "[plugin]")
    return output.getvalue()


@pytest.mark.parametrize("release", [False, True])
def test_encoded_refs_and_tags(provider, tmp_path: Path, release: bool) -> None:
    ref = "feature/a #?"
    encoded = quote(ref, safe="").encode()
    commit = "a" * 40

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path
        if path.endswith(b"/version"):
            return httpx.Response(200, json={"version": "1"})
        if b"/releases/" in path:
            assert path.endswith(b"/tags/" + encoded)
            return httpx.Response(200, json={"tag_name": ref})
        if b"/commits/" in path:
            assert path.endswith(b"/commits/" + encoded)
            return httpx.Response(200, json={"sha": commit})
        return httpx.Response(200, content=_zip())

    source = provider(
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
    )
    kwargs = {"release": ref} if release else {"requested_ref": ref}
    result = source.acquire(
        f"https://{source.spec.web_host}/owner/repo", tmp_path / "run", **kwargs
    )
    assert result.provenance.requested_ref == ref
    assert result.provenance.resolved_commit == commit


@pytest.mark.parametrize(
    "token,env,expected",
    [
        (None, "environment", "environment"),
        ("explicit", "environment", "explicit"),
        (None, "", None),
        ("", "environment", None),
    ],
)
def test_tokens(
    provider,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    token: str | None,
    env: str,
    expected: str | None,
) -> None:
    monkeypatch.setenv(provider.spec.token_env, env)

    def handler(request: httpx.Request) -> httpx.Response:
        authorization = request.headers.get("Authorization")
        assert authorization == (f"{provider.spec.auth_scheme} {expected}" if expected else None)
        return httpx.Response(404)

    source = provider(client=httpx.Client(transport=httpx.MockTransport(handler)), token=token)
    assert "environment" not in repr(source)
    assert "explicit" not in repr(source)
    with pytest.raises(SourceResolutionError):
        source.acquire(f"https://{source.spec.web_host}/owner/repo", tmp_path / "run")


@pytest.mark.parametrize("status", [403, 429])
def test_anonymous_rate_limit(
    provider, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, status: int
) -> None:
    monkeypatch.delenv(provider.spec.token_env, raising=False)
    source = provider(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(status, headers={"x-ratelimit-remaining": "0"})
            )
        )
    )
    with pytest.raises(SourceResolutionError, match=f"anonymous.*{source.spec.token_env}"):
        source.acquire(f"https://{source.spec.web_host}/owner/repo", tmp_path / "run")


def test_api_transport_error_wrapped_without_token(provider, tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("secret-token", request=request)

    source = provider(
        client=httpx.Client(transport=httpx.MockTransport(handler)), token="secret-token"
    )
    with pytest.raises(SourceResolutionError, match="API request failed") as caught:
        source.acquire(f"https://{source.spec.web_host}/owner/repo", tmp_path / "run")
    assert "secret-token" not in str(caught.value)


def test_api_redirects_not_followed(provider, tmp_path: Path) -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(302, headers={"location": "https://evil.test/steal"})

    source = provider(
        client=httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True),
        token="secret-token",
    )
    with pytest.raises(SourceResolutionError):
        source.acquire(f"https://{source.spec.web_host}/owner/repo", tmp_path / "run")
    assert "evil.test" not in seen


def test_close_preserves_injected_client(provider) -> None:
    client = httpx.Client()
    source = provider(client=client)
    source.close()
    assert not client.is_closed
    client.close()


def test_owned_close_http_errors_are_wrapped(provider, monkeypatch: pytest.MonkeyPatch) -> None:
    source = provider()

    def fail() -> None:
        raise httpx.CloseError("secret-token")

    monkeypatch.setattr(source._client, "close", fail)
    with pytest.raises(SourceResolutionError, match="close") as caught:
        source.close()
    assert "secret-token" not in str(caught.value)


@pytest.mark.parametrize("quota", ["download", "extraction"])
def test_source_enforces_custom_archive_limits(provider, tmp_path: Path, quota: str) -> None:
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
        return httpx.Response(200, content=_zip())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    source = provider(client=client)
    url = f"https://{source.spec.web_host}/owner/repo"
    with pytest.raises((SourceResolutionError, UnsafeArchiveError)):
        source.acquire(url, tmp_path / "limited", limits=limits)
    assert not (tmp_path / "limited/source").exists()
