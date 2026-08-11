from __future__ import annotations

import pytest
from pydantic import ValidationError

from redot_compat.models.manifest import PluginTestManifest, Probe, ProbeType


def test_manifest_accepts_only_declarative_probes() -> None:
    manifest = PluginTestManifest(
        plugin_id="example",
        probes=[
            Probe(type=ProbeType.CLASS_EXISTS, value="Node"),
            Probe(type=ProbeType.RESOURCE_EXISTS, value="res://addons/example/icon.svg"),
        ],
    )

    assert manifest.to_harness_payload()["plugin_id"] == "example"


@pytest.mark.parametrize("value", ["../../escape", "C:/absolute", "res://../escape"])
def test_resource_probe_rejects_escaping_paths(value: str) -> None:
    with pytest.raises(ValidationError):
        Probe(type=ProbeType.RESOURCE_EXISTS, value=value)


def test_manifest_forbids_arbitrary_fields() -> None:
    with pytest.raises(ValidationError):
        PluginTestManifest.model_validate(
            {"plugin_id": "example", "probes": [], "command": "rm -rf /"}
        )
