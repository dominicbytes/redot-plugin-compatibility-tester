from __future__ import annotations

from redot_compat.models import SourceKind
from redot_compat.sources.forge import ForgeSource, ForgeSpec


class GitHubSource(ForgeSource):
    spec = ForgeSpec(
        name="GitHub",
        web_host="github.com",
        source_kind=SourceKind.GITHUB,
        api_root="https://api.github.com",
        commit_path="commits",
        default_ref="HEAD",
        auth_scheme="Bearer",
        token_env="GITHUB_TOKEN",  # noqa: S106 - environment variable name
        base_headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        download_hosts=frozenset(
            {"objects.githubusercontent.com", "codeload.github.com", "api.github.com", "github.com"}
        ),
        default_archive_name="source.zip",
        asset_kind="release_asset",
        asset_noun="release asset",
    )

    def _base_capabilities(self) -> dict[str, str]:
        return {"api": "GitHub REST 2022-11-28"}

    def _commit_archive_url(self, owner: str, repository: str, api: str, commit: str) -> str:
        return f"{api}/zipball/{commit}"
