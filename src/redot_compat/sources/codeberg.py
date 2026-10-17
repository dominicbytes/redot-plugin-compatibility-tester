from __future__ import annotations

from redot_compat.models import SourceKind
from redot_compat.sources.forge import ForgeSource, ForgeSpec


class CodebergSource(ForgeSource):
    spec = ForgeSpec(
        name="Codeberg",
        web_host="codeberg.org",
        source_kind=SourceKind.CODEBERG,
        api_root="https://codeberg.org/api/v1",
        commit_path="git/commits",
        default_ref="main",
        auth_scheme="token",
        token_env="CODEBERG_TOKEN",  # noqa: S106 - environment variable name
        base_headers={"Accept": "application/json"},
        download_hosts=frozenset({"codeberg.org"}),
        default_archive_name="source.tar.gz",
        asset_kind="release_attachment",
        asset_noun="attachment",
    )

    def _base_capabilities(self) -> dict[str, str]:
        response = self._get(f"{self.spec.api_root}/version")
        version = "unknown"
        if response.status_code == 200:
            version = str(self._json_object(response, "version").get("version", "unknown"))
        return {"version": version, "archive_by_commit": "true"}

    def _commit_archive_url(self, owner: str, repository: str, api: str, commit: str) -> str:
        return f"https://codeberg.org/{owner}/{repository}/archive/{commit}.tar.gz"
