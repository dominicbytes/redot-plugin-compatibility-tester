from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]
NAME = "redot-plugin-compatibility-tester"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic local release evidence.")
    parser.add_argument("--output", type=Path, default=ROOT / "release")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    packages = _locked_packages()
    _write_json(output / "dependency-manifest.json", {"packages": packages})
    _write_json(output / "sbom.spdx.json", _spdx(packages))
    (output / "license-review.md").write_text(
        _license_review(packages), encoding="utf-8", newline="\n"
    )
    checksums = _checksums(output)
    (output / "SHA256SUMS").write_text(
        "".join(f"{digest}  {path}\n" for path, digest in checksums.items()),
        encoding="utf-8",
        newline="\n",
    )
    _write_json(
        output / "release-readiness.json",
        {
            "version": _project_version(),
            "release_status": "alpha-dry-run",
            "publish_authorized": False,
            "mandatory_blockers": [
                "canonical Linux G-01 CI capture is pending",
                "full G-04 phase and fixture matrix is pending",
                "G-06 platform and version 1.0 release audit is pending",
            ],
            "resolved_local_gates": [
                "G-02 exact engine provenance and deterministic snapshots",
                "G-03 Windows and Docker containment",
                "G-05 exact-control differential matrix",
                "optional exact Redot Mono fixture",
            ],
        },
    )


def _locked_packages() -> list[dict[str, Any]]:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    installed = {
        canonicalize_name(distribution.metadata["Name"]): distribution
        for distribution in importlib.metadata.distributions()
        if distribution.metadata["Name"]
    }
    records: list[dict[str, Any]] = []
    for package in lock.get("package", []):
        name = str(package["name"])
        version = str(package["version"])
        distribution = installed.get(canonicalize_name(name))
        metadata = distribution.metadata if distribution is not None else None
        records.append(
            {
                "name": name,
                "version": version,
                "license": _license(metadata),
                "homepage": _metadata_value(metadata, "Home-page"),
                "installed": distribution is not None,
            }
        )
    return sorted(records, key=lambda item: str(item["name"]).casefold())


def _license(metadata: Any) -> str:
    if metadata is None:
        return "NOASSERTION"
    expression = metadata.get("License-Expression")
    if expression:
        return str(expression).strip()
    value = metadata.get("License")
    if value and len(str(value).strip()) < 200:
        return str(value).strip()
    classifiers = metadata.get_all("Classifier") or []
    licenses = [
        item.removeprefix("License :: ") for item in classifiers if item.startswith("License :: ")
    ]
    return "; ".join(licenses) if licenses else "NOASSERTION"


def _metadata_value(metadata: Any, key: str) -> str | None:
    if metadata is None:
        return None
    value = metadata.get(key)
    return str(value) if value else None


def _spdx(packages: list[dict[str, Any]]) -> dict[str, Any]:
    version = _project_version()
    lock_hash = _sha256(ROOT / "uv.lock")
    created = datetime.fromtimestamp(int(os.environ.get("SOURCE_DATE_EPOCH", "0")), UTC)
    spdx_packages = []
    relationships = []
    for package in packages:
        safe_name = re.sub(r"[^A-Za-z0-9.-]", "-", str(package["name"]))
        spdx_id = f"SPDXRef-Package-{safe_name}"
        license_value = str(package["license"])
        spdx_packages.append(
            {
                "SPDXID": spdx_id,
                "name": package["name"],
                "versionInfo": package["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": license_value if _spdx_license(license_value) else "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": (f"pkg:pypi/{package['name']}@{package['version']}"),
                    }
                ],
            }
        )
        relationships.append(
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": spdx_id,
            }
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{NAME}-{version}",
        "documentNamespace": (f"https://github.com/dominicbytes/{NAME}/sbom/{version}/{lock_hash}"),
        "creationInfo": {
            "created": created.isoformat().replace("+00:00", "Z"),
            "creators": ["Tool: scripts/release_audit.py"],
        },
        "packages": spdx_packages,
        "relationships": relationships,
    }


def _spdx_license(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9.+-]+(?: (?:AND|OR) [A-Za-z0-9.+-]+)*", value))


def _license_review(packages: list[dict[str, Any]]) -> str:
    rows = ["| Package | Version | Declared license | Installed |", "|---|---:|---|:---:|"]
    for package in packages:
        rows.append(
            f"| `{package['name']}` | `{package['version']}` | "
            f"{str(package['license']).replace('|', '\\|')} | "
            f"{'yes' if package['installed'] else 'no'} |"
        )
    unknown = sum(package["license"] == "NOASSERTION" for package in packages)
    return (
        "# Locked dependency license review\n\n"
        "Generated from `uv.lock` and installed wheel metadata. This inventory is evidence, "
        "not legal advice. A release reviewer must resolve every `NOASSERTION`.\n\n"
        + "\n".join(rows)
        + f"\n\nUnresolved license declarations: **{unknown}**.\n"
    )


def _checksums(output: Path) -> dict[str, str]:
    candidates = [ROOT / "uv.lock", ROOT / "LICENSE"]
    candidates.extend(sorted((ROOT / "schemas").glob("*.json")))
    candidates.extend(sorted((ROOT / "dist").glob("*")))
    candidates.extend(
        path
        for path in sorted(output.glob("*"))
        if path.is_file() and path.name not in {"SHA256SUMS", "release-readiness.json"}
    )
    return {
        path.relative_to(ROOT).as_posix(): _sha256(path) for path in candidates if path.is_file()
    }


def _project_version() -> str:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(project["project"]["version"])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    main()
