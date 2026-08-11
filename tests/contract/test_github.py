from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import httpx

from redot_compat.sources.github import GitHubSource


def _archive() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("repo/addons/example/plugin.cfg", "[plugin]\nname='Example'\n")
    return output.getvalue()


def test_github_ref_resolves_to_full_commit_and_hashes_bytes(tmp_path: Path) -> None:
    commit = "a" * 40

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/v1.0.0"):
            return httpx.Response(200, json={"sha": commit}, request=request)
        if request.url.path.endswith(f"/zipball/{commit}"):
            return httpx.Response(
                200,
                headers={"content-type": "application/zip"},
                content=_archive(),
                request=request,
            )
        return httpx.Response(404, request=request)

    source = GitHubSource(client=httpx.Client(transport=httpx.MockTransport(handler)))
    resolved = source.acquire(
        "https://github.com/example/plugin", tmp_path / "run", requested_ref="v1.0.0"
    )

    assert resolved.provenance.resolved_commit == commit
    assert resolved.provenance.archive_sha256
    assert (resolved.content_root / "repo/addons/example/plugin.cfg").exists()


def test_github_release_asset_keeps_asset_identity_and_published_digest(tmp_path: Path) -> None:
    commit = "c" * 40
    archive = _archive()
    digest = hashlib.sha256(archive).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/releases/latest"):
            return httpx.Response(
                200,
                json={
                    "id": 77,
                    "tag_name": "v2.0.0",
                    "assets": [
                        {
                            "id": 88,
                            "name": "plugin.zip",
                            "size": len(archive),
                            "digest": f"sha256:{digest}",
                            "browser_download_url": "https://github.com/download/plugin.zip",
                        }
                    ],
                },
                request=request,
            )
        if path.endswith("/commits/v2.0.0"):
            return httpx.Response(200, json={"sha": commit}, request=request)
        if path == "/download/plugin.zip":
            return httpx.Response(
                200,
                headers={"content-type": "application/zip"},
                content=archive,
                request=request,
            )
        return httpx.Response(404, request=request)

    source = GitHubSource(client=httpx.Client(transport=httpx.MockTransport(handler)))
    resolved = source.acquire(
        "https://github.com/example/plugin",
        tmp_path / "run",
        release="latest",
        asset_pattern="*.zip",
    )

    assert resolved.provenance.release_id == "77"
    assert resolved.provenance.release_asset_name == "plugin.zip"
    assert resolved.provenance.published_digest == f"sha256:{digest}"
