from __future__ import annotations

import hashlib
import platform
import re
from dataclasses import dataclass
from pathlib import Path

from redot_compat.archive.hash import sha256_file
from redot_compat.models.engine import EngineIdentity

_REDOT_COMPATIBILITY = {"26.2": "4.5.2"}
_VERSION_PATTERN = re.compile(r"(?P<version>\d+\.\d+(?:\.\d+)?(?:[^\s]*)?)")


@dataclass(frozen=True)
class ParsedEngineVersion:
    product_name: str
    product_version: str
    compatibility_version: str | None


def parse_engine_version(output: str, *, product_hint: str) -> ParsedEngineVersion:
    normalized = output.strip().splitlines()[0] if output.strip() else ""
    match = _VERSION_PATTERN.search(normalized)
    if match is None:
        raise ValueError("engine version output did not contain a version")
    version = match.group("version").rstrip(".,;)")
    hint = product_hint.casefold()
    if hint == "redot":
        release = ".".join(version.split(".")[:2])
        return ParsedEngineVersion("Redot", version, _REDOT_COMPATIBILITY.get(release))
    if hint == "godot":
        compatibility = ".".join(version.split(".")[:3])
        return ParsedEngineVersion("Godot", version, compatibility)
    raise ValueError("product_hint must be 'redot' or 'godot'")


def identify_engine(
    binary: Path,
    *,
    version_output: str,
    help_output: str,
    product_hint: str,
) -> EngineIdentity:
    resolved = binary.resolve(strict=True)
    parsed = parse_engine_version(version_output, product_hint=product_hint)
    machine = platform.machine().lower().replace("amd64", "x86_64")
    lower_evidence = f"{resolved.name} {version_output}".casefold()
    return EngineIdentity(
        product_name=parsed.product_name,
        product_version=parsed.product_version,
        compatibility_version=parsed.compatibility_version,
        binary_path=str(resolved),
        binary_sha256=sha256_file(resolved),
        platform=platform.system().lower(),
        architecture=machine,
        precision="double" if "double" in lower_evidence else "single",
        is_dotnet="mono" in lower_evidence or ".net" in lower_evidence,
        version_output=version_output.strip(),
        help_output_sha256=hashlib.sha256(help_output.encode("utf-8")).hexdigest(),
    )
