from __future__ import annotations

import io
import tarfile
from pathlib import Path

import httpx

from redot_compat.sources.codeberg import CodebergSource


def _archive() -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        content = b"[plugin]\nname='Example'\n"
        info = tarfile.TarInfo("repo/addons/example/plugin.cfg")
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def test_codeberg_records_version_capability_and_commit(tmp_path: Path) -> None:
    commit = "b" * 40

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/version":
            return httpx.Response(200, json={"version": "11.0.0"}, request=request)
        if path.endswith("/git/commits/v2.0.0"):
            return httpx.Response(200, json={"sha": commit}, request=request)
        if path.endswith(f"/archive/{commit}.tar.gz"):
            return httpx.Response(
                200,
                headers={"content-type": "application/gzip"},
                content=_archive(),
                request=request,
            )
        return httpx.Response(404, request=request)

    source = CodebergSource(client=httpx.Client(transport=httpx.MockTransport(handler)))
    resolved = source.acquire(
        "https://codeberg.org/example/plugin", tmp_path / "run", requested_ref="v2.0.0"
    )

    assert resolved.provenance.resolved_commit == commit
    assert resolved.provider_capabilities["version"] == "11.0.0"
    assert (resolved.content_root / "repo/addons/example/plugin.cfg").exists()


def test_codeberg_release_attachment_is_distinct_from_source_archive(tmp_path: Path) -> None:
    commit = "d" * 40
    archive = _archive()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v1/version":
            return httpx.Response(200, json={"version": "11.0.0"}, request=request)
        if path.endswith("/releases/tags/v3.0.0"):
            return httpx.Response(
                200,
                json={
                    "id": 91,
                    "tag_name": "v3.0.0",
                    "assets": [
                        {
                            "id": 92,
                            "name": "plugin.tar.gz",
                            "browser_download_url": (
                                "https://codeberg.org/example/plugin/releases/download/"
                                "v3.0.0/plugin.tar.gz"
                            ),
                        }
                    ],
                },
                request=request,
            )
        if path.endswith("/git/commits/v3.0.0"):
            return httpx.Response(200, json={"sha": commit}, request=request)
        if path.endswith("/releases/download/v3.0.0/plugin.tar.gz"):
            return httpx.Response(
                200,
                headers={"content-type": "application/gzip"},
                content=archive,
                request=request,
            )
        return httpx.Response(404, request=request)

    source = CodebergSource(client=httpx.Client(transport=httpx.MockTransport(handler)))
    resolved = source.acquire(
        "https://codeberg.org/example/plugin",
        tmp_path / "run",
        release="v3.0.0",
        asset_pattern="*.tar.gz",
    )

    assert resolved.provenance.release_id == "91"
    assert resolved.provenance.release_asset_name == "plugin.tar.gz"
    assert resolved.provider_capabilities["artifact_kind"] == "release_attachment"
