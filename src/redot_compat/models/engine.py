from __future__ import annotations

from pydantic import Field

from redot_compat.models.base import ContractModel


class EngineIdentity(ContractModel):
    product_name: str
    product_version: str
    compatibility_version: str | None = None
    binary_path: str
    binary_sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    platform: str
    architecture: str
    precision: str = "single"
    is_dotnet: bool = False
    version_output: str
    help_output_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    extension_api_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    extension_api_path: str | None = None
    source_archive_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    source_revision: str | None = None
