from __future__ import annotations

import pytest
from pydantic import ValidationError

from redot_compat.constants import BATCH_SCHEMA_VERSION
from redot_compat.models.batch import BatchItem, BatchManifest


def test_batch_manifest_bounds_concurrency_and_requires_unique_ids() -> None:
    manifest = BatchManifest(
        concurrency=2,
        items=[BatchItem(id="one", source="./one"), BatchItem(id="two", source="./two")],
    )

    assert manifest.concurrency == 2

    with pytest.raises(ValidationError):
        BatchManifest(
            concurrency=9,
            items=[BatchItem(id="same", source="./one"), BatchItem(id="same", source="./two")],
        )


@pytest.mark.parametrize("version", [1, "1.1.0"])
def test_batch_manifest_accepts_current_and_legacy_versions(version: int | str) -> None:
    manifest = BatchManifest.model_validate(
        {"schema_version": version, "items": [{"id": "one", "source": "./one"}]}
    )
    assert manifest.schema_version == BATCH_SCHEMA_VERSION == "1.1.0"
    assert isinstance(manifest.model_dump()["schema_version"], str)


@pytest.mark.parametrize("version", [True, 2, "2.0.0", "invalid"])
def test_batch_manifest_rejects_unsupported_versions(version: object) -> None:
    with pytest.raises(ValidationError):
        BatchManifest.model_validate(
            {"schema_version": version, "items": [{"id": "one", "source": "./one"}]}
        )
